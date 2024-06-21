#!/usr/bin/python3

from config import *
from os.path import join
from evaluate import Evaluator
from source_manager import SourceManager
import logging
import toml
import sys

logging.basicConfig(level=logging.WARNING)
logging.getLogger("LiteLLM").setLevel(logging.WARNING)

manager = SourceManager()
evaluator = Evaluator()


for eval_name in sys.argv[1:]:
    print(eval_name)
    eval_results = {}
    with open(join(EVALS_FOLDER, eval_name + ".toml"), "r") as eval_file:
        eval = toml.load(eval_file)
    for source in eval["requires"]:
        manager.load_source(source)
    for section_id, section in eval.items():
        correct = 0
        incorrect = 0
        correct_a = 0
        correct_b = 0
        incorrect_a = 0
        incorrect_b = 0
        if section_id == "requires":
            continue
        print(section_id)
        for match in section:
            print(f"{match['winner']} vs. {match['loser']}")
            expected_winner = manager.get_character(match["winner"])
            expected_loser = manager.get_character(match["loser"])
            winner_a, loser_a = evaluator.evaluate(expected_winner, expected_loser)
            if winner_a == expected_winner:
                print("A Correct")
                correct += 1
                correct_a += 1
            else:
                print("A Incorrect")
                incorrect += 1
                incorrect_a += 1
            winner_b, loser_b = evaluator.evaluate(expected_loser, expected_winner)
            if winner_b == expected_winner:
                print("B Correct")
                correct += 1
                correct_b += 1
            else:
                print("B Incorrect")
                incorrect += 1
                incorrect_b += 1
        eval_results[section_id] = {
            "correct": correct,
            "incorrect": incorrect,
            "correct_a": correct_a,
            "correct_b": correct_b,
            "incorrect_a": incorrect_a,
            "incorrect_b": incorrect_b,
        }
    print(eval_results)
