#!/usr/bin/python3

from aiolimiter import AsyncLimiter
from character import CharacterId
from config import *
from os.path import join
from evaluate import Evaluator
from source_manager import SourceManager
import logging
import toml
import sys
import asyncio

logging.basicConfig(level=logging.INFO)
logging.getLogger("LiteLLM").setLevel(logging.WARNING)

manager = SourceManager()
evaluator = Evaluator()

rate_limit = AsyncLimiter(1, 10)


async def run_match(match: dict[str, str]) -> tuple[bool | None, bool | None]:
    expected_winner = manager.get_character(CharacterId.from_str(match["winner"]))
    expected_loser = manager.get_character(CharacterId.from_str(match["loser"]))
    # Run "A" eval
    w_l, _, _ = await evaluator.evaluate(
        expected_winner, expected_loser, False, rate_limit, verbose=True
    )
    if w_l is None:
        result_a = None
    elif w_l[0] == expected_winner:
        result_a = True
    else:
        result_a = False
    # Run "B" eval
    w_l, _, _ = await evaluator.evaluate(
        expected_loser, expected_winner, False, rate_limit, verbose=True
    )
    if w_l is None:
        result_b = None
    elif w_l[0] == expected_winner:
        result_b = True
    else:
        result_b = False
    return (result_a, result_b)


async def run_eval(eval: dict[str, list[dict[str, str]]]):
    section_results = {}
    for section_id, section in eval.items():
        if section_id == "requires":
            continue
        correct = 0
        incorrect = 0
        indeterminate = 0
        correct_a = 0
        correct_b = 0
        incorrect_a = 0
        incorrect_b = 0
        indeterminate_a = 0
        indeterminate_b = 0
        results = await asyncio.gather(*[run_match(match) for match in section])
        # Process results to create stats
        for result in results:
            for is_b, round_result in enumerate(result):
                if round_result == None:
                    if is_b:
                        indeterminate_b += 1
                    else:
                        indeterminate_a += 1
                elif round_result == True:
                    correct += 1
                    if is_b:
                        correct_b += 1
                    else:
                        correct_a += 1
                else:
                    incorrect += 1
                    if is_b:
                        incorrect_b += 1
                    else:
                        incorrect_a += 1
        section_results[section_id] = {
            "correct": correct,
            "incorrect": incorrect,
            "indeterminate": indeterminate,
            "correct_a": correct_a,
            "correct_b": correct_b,
            "incorrect_a": incorrect_a,
            "incorrect_b": incorrect_b,
            "indeterminate_a": indeterminate_a,
            "indeterminate_b": indeterminate_b,
        }
    return section_results


async def main():
    for eval_name in sys.argv[1:]:
        print(eval_name)
        with open(join(EVALS_FOLDER, eval_name + ".toml"), "r") as eval_file:
            eval = toml.load(eval_file)
        for source in eval["requires"]:
            await manager.load_source(source)
        eval_results = await run_eval(eval)
        print(eval_results)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
