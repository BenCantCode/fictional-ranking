from __future__ import annotations
from aiolimiter import AsyncLimiter
from jinja2 import FileSystemLoader, Environment, BaseLoader
from config import *
from character import Character, CharacterId
import toml
from exceptions import *
import os.path
import time
from litellm import (
    acompletion,
    completion_cost,
    ModelResponse,
    Choices,
    get_max_tokens,
    cost_per_token,
    token_counter,
    Router,
    APIConnectionError,
    RateLimitError,
    BadRequestError,
)
from os.path import join
import logging
from typing import Any, cast, TYPE_CHECKING
import random

from match import MatchSettings

logger = logging.getLogger(__name__)


class Evaluator:
    def __init__(
        self,
        prompt_file: str | None = PROMPT,
        prompt_raw: str | None = None,
        winner_prefix: str | None = None,
        template_folder: str = PROMPTS_FOLDER,
        stop: list[str] = [],
        information_file: str = INFORMATION_FILE,
        information_raw: dict | None = None,
    ):
        prompt_id = None
        prompt_version = None
        information_id = None
        information_version = None
        env = Environment(loader=FileSystemLoader(template_folder), autoescape=False)
        if prompt_raw:
            self.template = env.from_string(prompt_raw)
            if winner_prefix == None:
                raise ValueError("No winner prefix provided!")
            self.winner_prefix = winner_prefix
            self.stop = stop
        else:
            if not prompt_file:
                raise ValueError("No prompt file or raw prompt provided.")
            with open(join(template_folder, prompt_file), "r") as file:
                prompt_meta = toml.load(file)
                self.template = env.get_template(prompt_meta["template_file"])
                prompt_id = prompt_meta["id"]
                prompt_version = prompt_meta["version"]
                self.winner_prefix = prompt_meta["winner_prefix"]
                self.stop = prompt_meta["stop"]
        if not information_raw:
            with open(information_file, "r") as file:
                information_raw = toml.load(file)
            information_id = information_raw["id"]  # type: ignore
            information_version = information_raw["version"]  # type: ignore
        self.information = information_raw
        self.prompt_id = prompt_id
        self.prompt_version = prompt_version
        self.prompt_file = prompt_file
        self.information_id = information_id
        self.information_version = information_version
        self.information_file = information_file

    def to_object(self):
        return {
            "prompt": {
                "id": self.prompt_id,
                "version": self.prompt_version,
                "file": self.prompt_file,
            },
            "information": {
                "id": self.information_id,
                "version": self.information_version,
                "file": self.information_file,
            },
        }

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
            prompt_file=object["prompt"]["file"],
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

    # https://stackoverflow.com/a/22096493
    @staticmethod
    def _name_parts(name: str) -> set[str]:
        return set(
            ("".join([c if c.isalnum() else " " for c in name.lower()])).split(" ")
        )

    def _full_name(self, name: str, source_id: str):
        return f"{name} ({self.information[source_id]['name']})"

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
            expected_a = self._full_name(character_a.name, character_a.source_id)
            expected_b = self._full_name(character_b.name, character_b.source_id)
        # If the names match exactly, use them
        if winner_raw == expected_a:
            return character_a
        if winner_raw == expected_b:
            return character_b
        logger.warn("Complex result: %s", winner_raw)
        # If they don't match, return whichever has more overlap
        overlap_a = 0
        overlap_b = 0
        winner_raw_parts = self._name_parts(winner_raw)
        for alias in [character_a.name] + character_a.aliases:
            overlap_a = max(
                overlap_a,
                len(
                    set(self._name_parts(self._full_name(alias, character_a.source_id)))
                    & winner_raw_parts
                ),
            )
        for alias in [character_b.name] + character_b.aliases:
            overlap_b = max(
                overlap_b,
                len(
                    set(self._name_parts(self._full_name(alias, character_b.source_id)))
                    & winner_raw_parts
                ),
            )
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
        rate_limit: AsyncLimiter,
        num_retries: int = NUM_RETRIES,
        **completion_args,
    ) -> ModelResponse:
        attempts = 0
        while True:
            try:
                async with rate_limit:
                    return await acompletion(
                        model=model, messages=messages, **completion_args
                    )  # type: ignore
                raise Exception("Impossible?")
            except (APIConnectionError, RateLimitError, BadRequestError) as e:
                logger.warn("Completion attempt failed: %s", str(e))
                logger.warn("Retrying...")
                attempts += 1
                if attempts == num_retries:
                    raise e

    async def evaluate(
        self,
        character_a: Character,
        character_b: Character,
        dry_run: bool,
        rate_limit: AsyncLimiter,
        model: str = MODEL,
        completion_args: dict = COMPLETION_ARGS,
        max_characters: int = MAX_CHARACTERS,
        max_tokens: int | None = MAX_TOKENS,
        max_cost: float | None = MAX_COST,
        debug_dump: bool = DEBUG_DUMP,
        debug_filter: list[CharacterId] | None = DEBUG_DUMP_FILTER,
        debug_dump_prefix: str = "debug",
        debug_folder: str = DEBUG_FOLDER,
        verbose: bool = False,
    ) -> tuple[tuple[Character, Character] | None, float, MatchSettings]:
        match_settings = MatchSettings(
            model,
            self.prompt_id,
            self.prompt_version,
            self.information_id,
            self.information_version,
        )
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
            return (winner, loser), estimated_cost, match_settings
        res = await self.get_completion(model, messages, rate_limit, **completion_args)
        res_text: str | None = res.choices[0].message.content  # type: ignore
        cost = completion_cost(res, model)
        if debug_dump:
            if (
                (not debug_filter)
                or character_a.id in debug_filter
                or character_b.id in debug_filter
            ):
                with open(
                    join(
                        debug_folder,
                        f"{debug_dump_prefix}-{str(character_a.id).replace(os.path.sep, '-')}-vs-{str(character_b.id).replace(os.path.sep, '-')}.txt",
                    ),
                    "w",
                ) as file:
                    file.write(res_text or "")
        winner = None
        if res_text == None:
            if verbose:
                logger.info(f"No result for %s vs. %s", character_a.id, character_b.id)
            return (None, cost, match_settings)
        else:
            try:
                winner = self.parse_result(res_text, character_a, character_b)
                loser = character_a if character_b == winner else character_b
                if verbose:
                    logger.info(f"W: %s, L: %s", winner.id, loser.id)
                return ((winner, loser), cost, match_settings)
            except InvalidResult as e:
                if verbose:
                    logger.info("Invalid result: %s", str(e))
                return (None, cost, match_settings)
