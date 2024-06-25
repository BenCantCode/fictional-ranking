from __future__ import annotations
from aiolimiter import AsyncLimiter
from jinja2 import FileSystemLoader, Environment, BaseLoader
from openai import APIConnectionError
from config import *
from character import Character
import toml
from exceptions import *
from litellm import (
    acompletion,
    completion_cost,
    ModelResponse,
    Choices,
    get_max_tokens,
    cost_per_token,
    token_counter,
)
from os.path import join
import logging
from typing import Any, cast, TYPE_CHECKING
import random

logger = logging.getLogger(__name__)


class Evaluator:
    def __init__(
        self,
        prompt: str = PROMPT,
        template: str | None = None,
        winner_prefix: str | None = None,
        template_folder: str = PROMPTS_FOLDER,
        stop: list[str] = [],
        information: dict | None = None,
        information_file: str = INFORMATION_FILE,
    ):
        prompt_id = None
        prompt_version = None
        information_id = None
        information_version = None
        using_prompt_file = not bool(template)
        using_informaton_file = not bool(information)
        env = Environment(loader=FileSystemLoader(template_folder), autoescape=False)
        if template:
            self.template = env.from_string(template)
            if winner_prefix == None:
                raise Exception("No winner prefix provided!")
            self.winner_prefix = winner_prefix
            self.stop = stop
        else:
            with open(join(template_folder, prompt), "r") as file:
                prompt_meta = toml.load(file)
                self.template = env.get_template(prompt_meta["template_file"])
                prompt_id = prompt_meta["id"]
                prompt_version = prompt_meta["version"]
                self.winner_prefix = prompt_meta["winner_prefix"]
                self.stop = prompt_meta["stop"]
        if not information:
            with open(information_file, "r") as file:
                information = toml.load(file)
        information_id = information["id"]  # type: ignore
        information_version = information["version"]  # type: ignore
        self.information = information
        self.object = {
            "prompt": {"id": prompt_id, "version": prompt_version, file: prompt},
            "information": {
                "id": information_id,
                "version": information_version,
                file: information_file,
            },
        }

    def to_object(self):
        return self.object

    @staticmethod
    def from_object(object: dict[str, Any]) -> Evaluator:
        if object["information"]["file"] == None:
            raise NotImplementedError(
                "Custom information manually provided to previous run (i.e. not in a file), so it cannot be deserialized."
            )
        if object["prompt"]["file"] == None:
            raise NotImplementedError(
                "Custom prompt manually provided to previous run (i.e. not in a file), so it cannot be deserialized."
            )
        return Evaluator(
            prompt=object["prompt"]["file"],
            information_file=object["information"]["file"],
        )

    def format(
        self,
        character_a: Character,
        character_b: Character,
        model: str = MODEL,
        max_characters: int = MAX_CHARACTERS,
        max_tokens: int | None = MAX_TOKENS,
        max_cost: float | None = MAX_COST,
    ) -> str:
        if character_a.id.source_id == character_b.source_id:
            character_a_name = character_a.name
            character_b_name = character_b.name
        else:
            character_a_name = f"{character_a.name} ({self.information[character_a.source_id]['name']})"
            character_b_name = f"{character_b.name} ({self.information[character_b.source_id]['name']})"

        character_a_description = character_a.abridged_text(
            model, max_characters, max_tokens, max_cost
        )
        character_b_description = character_b.abridged_text(
            model, max_characters, max_tokens, max_cost
        )
        return self.template.render(
            {
                "character_a": {
                    "name": character_a_name,
                    "description": character_a_description,
                },
                "franchise_a": self.information[character_a.source_id],
                "character_b": {
                    "name": character_b_name,
                    "description": character_b_description,
                },
                "franchise_b": self.information[character_b.source_id],
            }
        )

    def parse_result(
        self, response: str, character_a: Character, character_b: Character
    ) -> Character:
        winner_index = response.find(self.winner_prefix) + len(self.winner_prefix)
        winner_raw = response[winner_index:]
        winner_raw = winner_raw.split("\n")[0]
        if not winner_raw:
            raise InvalidResult("No winner found.")
        if character_a.source_id == character_b.source_id:
            expected_a = character_a.name
            expected_b = character_b.name
        else:
            expected_a = f"{character_a.name} ({self.information[character_a.source_id]['name']})"
            expected_b = f"{character_b.name} ({self.information[character_b.source_id]['name']})"
        # If the names match exactly, use them
        if winner_raw == expected_a:
            return character_a
        if winner_raw == expected_b:
            return character_b
        # If they don't match, return whichever has more overlap
        overlap_a = len(set(expected_a.split(" ")) & set(winner_raw.split(" ")))
        overlap_b = len(set(expected_b.split(" ")) & set(winner_raw.split(" ")))
        if overlap_a > overlap_b:
            return character_a
        if overlap_b > overlap_a:
            return character_b
        # TODO: Implement aliases
        raise InvalidResult(f"Invalid winner: {winner_raw}")

    async def get_completion(
        self,
        model: str,
        messages: list,
        rate_limit: AsyncLimiter | None,
        num_retries: int = NUM_RETRIES,
        **completion_args,
    ):
        for i in range(num_retries):
            try:
                coroutine = acompletion(
                    model,
                    messages,
                    stop=self.stop,
                    stream=False,
                    **completion_args,
                )
                if rate_limit:
                    async with rate_limit:
                        return await coroutine
                else:
                    return await coroutine
            except APIConnectionError as e:
                if i == num_retries - 1:
                    raise e
            break

    async def evaluate(
        self,
        character_a: Character,
        character_b: Character,
        dry_run: bool,
        model: str = MODEL,
        completion_args: dict = COMPLETION_ARGS,
        max_characters: int = MAX_CHARACTERS,
        max_tokens: int | None = MAX_TOKENS,
        max_cost: float | None = MAX_COST,
        debug_dump: bool = DEBUG_DUMP,
        debug_folder: str = DEBUG_FOLDER,
        rate_limit: AsyncLimiter | None = None,
        verbose: bool = False,
    ) -> tuple[tuple[Character, Character] | None, float]:
        prompt_text = self.format(
            character_a,
            character_b,
            model,
            max_characters,
            max_tokens,
            max_cost,
        )
        if debug_dump:
            with open(join(debug_folder, "last_prompt.txt"), "w") as file:
                file.write(prompt_text)
        messages = [
            {
                "role": "user",
                "content": prompt_text,
            },
        ]
        if dry_run:
            if verbose:
                logger.info("%s vs. %s", character_a.id, character_b.id)
            estimated_response_length = get_max_tokens(model) or 4096
            estimated_cost = sum(
                cost_per_token(
                    model,
                    prompt_tokens=token_counter(model=model, text=prompt_text),
                    completion_tokens=estimated_response_length,
                )
            )
            if verbose:
                logger.info("Predicted cost: %f", estimated_cost)
            # Random winner
            winner = character_a if random.randint(0, 1) == 0 else character_b
            loser = character_a if character_b == winner else character_b
            return (winner, loser), estimated_cost
        res = await self.get_completion(model, messages, rate_limit, **completion_args)
        res_text: str | None = res.choices[0].message.content  # type: ignore
        cost = completion_cost(res, model)
        if debug_dump:
            with open(join(debug_folder, "last_response.txt"), "w") as file:
                file.write(res_text or "")
        winner = None
        if res_text == None:
            if verbose:
                logger.info(f"No result for %s vs. %s", character_a.id, character_b.id)
            return (None, cost)
        else:
            try:
                winner = self.parse_result(res_text, character_a, character_b)
                loser = character_a if character_b == winner else character_b
                if verbose:
                    logger.info(f"W: %s, L: %s", winner.id, loser.id)
                return ((winner, loser), cost)
            except InvalidResult as e:
                if verbose:
                    logger.info("Invalid result: %s", str(e))
                return (None, cost)
