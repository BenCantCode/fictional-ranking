from jinja2 import FileSystemLoader, Environment, BaseLoader
from config import *
from character import Character
import toml
from exceptions import *
from litellm import completion, completion_cost
from os.path import join
import logging

logger = logging.getLogger(__name__)


class Evaluator:
    def __init__(
        self,
        prompt: str = PROMPT,
        template: str = None,
        winner_prefix: str = None,
        template_folder: str = PROMPTS_FOLDER,
        stop: list[str] = [],
        information: dict = None,
        information_file: str = INFORMATION_FILE,
    ):
        env = Environment(loader=FileSystemLoader(template_folder), autoescape=False)
        if template:
            self.template = env.from_string(template)
            if winner_prefix == None:
                raise Exception("No winner prefix provided!")
            self.winner_prefix = winner_prefix
            self.stop = stop
        else:
            with open(join(template_folder, prompt), "r") as file:
                prompt = toml.load(file)
                self.template = env.get_template(prompt["template_file"])
                self.winner_prefix = prompt["winner_prefix"]
                self.stop = prompt["stop"]
        if information:
            self.information = information
        else:
            with open(information_file, "r") as file:
                self.information = toml.load(file)

    def format(
        self,
        character_a: Character,
        character_b: Character,
        model: str = MODEL,
        max_characters: int = MAX_CHARACTERS,
        max_tokens: int = MAX_TOKENS,
        max_cost: float = MAX_COST,
    ) -> str:
        if character_a.source == character_b.source:
            character_a_name = character_a.name
            character_b_name = character_b.name
        else:
            character_a_name = (
                f"{character_a.name} ({self.information[character_a.source]['name']})"
            )
            character_b_name = (
                f"{character_b.name} ({self.information[character_b.source]['name']})"
            )

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
                "franchise_a": self.information[character_a.source],
                "character_b": {
                    "name": character_b_name,
                    "description": character_b_description,
                },
                "franchise_b": self.information[character_b.source],
            }
        )

    def parse_result(
        self, response: str, character_a: Character, character_b: Character
    ) -> Character | None:
        winner_index = response.find(self.winner_prefix) + len(self.winner_prefix)
        winner_raw = response[winner_index:]
        winner_raw = winner_raw.split("\n")[0]
        if not winner_raw:
            raise InvalidResult("No winner found.")
        if character_a.source == character_b.source:
            expected_a = character_a.name
            expected_b = character_b.name
        else:
            expected_a = (
                f"{character_a.name} ({self.information[character_a.source]['name']})"
            )
            expected_b = (
                f"{character_b.name} ({self.information[character_b.source]['name']})"
            )
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

    def evaluate(
        self,
        character_a: Character,
        character_b: Character,
        model: str = MODEL,
        completion_args: dict = COMPLETION_ARGS,
        max_characters: int = MAX_CHARACTERS,
        max_tokens: int = MAX_TOKENS,
        max_cost: float = MAX_COST,
        debug_dump: bool = DEBUG_DUMP,
        debug_folder: str = DEBUG_FOLDER,
    ) -> tuple[Character, Character]:
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
        res = completion(
            model,
            messages=[
                {
                    "role": "user",
                    "content": prompt_text,
                },
            ],
            stop=self.stop,
            **completion_args,
        )
        res_text = res.choices[0].message.content
        if debug_dump:
            with open(join(debug_folder, "last_response.txt"), "w") as file:
                file.write(res_text)
        winner = self.parse_result(res_text, character_a, character_b)
        loser = character_a if character_b == winner else character_b
        logger.info(f"W: %s, L: %s", winner.id, loser.id)
        try:
            logger.info(f"Cost: %f", completion_cost(res, model))
        except:
            pass
        return (winner, loser)
