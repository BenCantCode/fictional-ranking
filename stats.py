from config import *
from evaluate import Evaluator
from source_manager import SourceManager
import logging
from character import CharacterId
from run import Run
from generator import Generator
from character_filter import SourceFilter, CharacterIdFilter, EverythingFilter
from rating import rate_characters
from match_filter import (
    InvertFilter,
    DuplicateMatchInRunFilter,
    AndFilter,
    SelfMatchFilter,
    CharacterMatchesThresholdFilter,
)
from matchmaking import PowermatchingMatchmaker, RandomMatchmaker
from db import RunsDatabase
import asyncio

logging.basicConfig(level=logging.INFO)
logging.getLogger("LiteLLM").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

db = RunsDatabase()
source_manager = SourceManager()
source_manager.load_source("one_piece")
evaluator = Evaluator()
character_filter = EverythingFilter()
# character_filter = CharacterIdFilter(
#     [
#         CharacterId("one_piece", "Roronoa Zoro"),
#         CharacterId("one_piece", "Marshall D. Teach"),
#         CharacterId("one_piece", "Trafalgar D. Water Law"),
#         CharacterId("one_piece", "Queen"),
#         CharacterId("one_piece", "Marco"),
#         CharacterId("one_piece", "Jinbe"),
#         CharacterId("one_piece", "Yamato"),
#         CharacterId("one_piece", "Arlong"),
#         CharacterId("one_piece", "Charlotte Linlin"),
#         CharacterId("one_piece", "Stussy"),
#         CharacterId("one_piece", "Bepo"),
#     ]
# )
match_filter = (
    ~SelfMatchFilter()
    & ~DuplicateMatchInRunFilter()
    & ~CharacterMatchesThresholdFilter(2)
)
matchmaker = RandomMatchmaker(1)
# matchmaker = PowermatchingMatchmaker(rate_characters(list(db.get_results())))
generator = Generator(
    character_filter, match_filter, matchmaker, source_manager.source_versions
)
run = Run("one_piece_initial", generator, evaluator, db, False)
results, cost = asyncio.run(run.run(source_manager, verbose=True))
with open("results.txt", "w") as file:
    for result in results:
        file.write(
            f"{result.character_a.id} vs. {result.character_b.id}: {result.outcome}\n"
        )
