from config import *
from evaluate import Evaluator
from source_manager import SourceManager
import logging
from character import Character

logging.basicConfig(level=logging.INFO)
logging.getLogger("LiteLLM").setLevel(logging.WARNING)

manager = SourceManager()
evaluator = Evaluator()

manager.load_source("marvel")

num = 0
with open("marvel_names.txt", "w") as file:
    for character in manager.all_characters():
        file.write(character.name + "\n")
        num += 1

print(num)

# a = manager.get_character(character_a)
# b = manager.get_character(character_b)

# result: Character = evaluator.evaluate(a, b)
# print("Winner:", result.name)

# print(result)
