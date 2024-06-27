from aiolimiter import AsyncLimiter
from config import *
from evaluate import Evaluator
from source_manager import SourceManager
import logging
from character import CharacterId
from run import Run
from generator import Generator
from character_filter import (
    SourceFilter,
    CharacterIdFilter,
    EverythingFilter,
    RatingFilter,
)
from rating import rate_characters
from match_filter import (
    DuplicateMatchInPriorRunFilter,
    InvertFilter,
    DuplicateMatchInRunFilter,
    AndFilter,
    SelfMatchFilter,
    CharacterMatchesThresholdFilter,
)
from matchmaking import PowermatchingMatchmaker, RandomMatchmaker
from db import RunsDatabase
import asyncio
import json

logging.basicConfig(level=logging.INFO)
logging.getLogger("LiteLLM").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("LiteLLM Router").setLevel(logging.WARNING)

db = RunsDatabase()
source_manager = SourceManager()
source_manager.load_source("one_piece")
evaluator = Evaluator()

results = list(db.get_results())
ratings = rate_characters(results)

character_filter = ~CharacterIdFilter(
    [
        CharacterId("one_piece", "Rocks Pirates"),
        CharacterId("one_piece", "Impel Down"),
        CharacterId("one_piece", "Rock"),
    ]
) & RatingFilter(5.6, ratings)
match_filter = (
    ~SelfMatchFilter()
    & ~DuplicateMatchInRunFilter()
    & ~DuplicateMatchInPriorRunFilter(results, threshold=2)
    & ~CharacterMatchesThresholdFilter(2)
)
# matchmaker = RandomMatchmaker(1)

matchmaker = PowermatchingMatchmaker(ratings)
generator = Generator(
    character_filter, match_filter, matchmaker, source_manager.source_versions
)
# run = db.get_run_by_name("one_piece_powermatched_5", source_manager)
run = Run("one_piece_top_tier_2", generator, evaluator, db, False)
results, cost = asyncio.run(run.start(source_manager, AsyncLimiter(1, 4), verbose=True))
with open("results.txt", "w") as file:
    for result in run.results:
        file.write(
            f"{result.character_a.id} vs. {result.character_b.id}: {result.outcome}\n"
        )

results = list(db.get_results())
ratings = rate_characters(results)
with open("ratings.txt", "w") as file:
    for character_id, rating in sorted(
        list(ratings.items()),
        key=lambda x: x[1],
    ):
        file.write(f"{character_id}: {rating}\n")
