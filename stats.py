from aiolimiter import AsyncLimiter
from config import *
from evaluate import Evaluator
from source_manager import SourceManager
import logging
from character import CharacterId
from run import Run
from generator import Generator
from character_filter import (
    CHARACTER_FILTER_TYPE_REGISTRAR,
    SourceFilter,
    CharacterIdFilter,
    EverythingFilter,
    RatingFilter,
)
from rating import rate_characters
from match_filter import (
    MATCH_FILTER_TYPE_REGISTRAR,
    DuplicateMatchInPriorRunFilter,
    InvertFilter,
    DuplicateMatchInRunFilter,
    AndFilter,
    SelfMatchFilter,
    CharacterMatchesThresholdFilter,
)
from matchmaking import (
    MATCHMAKER_TYPE_REGISTRAR,
    PowermatchingMatchmaker,
    RandomMatchmaker,
)
from db import RunsDatabase
import asyncio
import json

logging.basicConfig(level=logging.INFO)
logging.getLogger("LiteLLM").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("LiteLLM Router").setLevel(logging.WARNING)


async def main():
    db = RunsDatabase()
    source_manager = SourceManager()
    await source_manager.load_source("one_piece")

    evaluator = Evaluator()

    results = list(db.get_results())
    ratings = rate_characters(results)

    character_filter = RatingFilter(5000, ratings)
    match_filter = (
        ~SelfMatchFilter()
        & ~DuplicateMatchInRunFilter()
        & ~DuplicateMatchInPriorRunFilter(results, threshold=3)
        & ~CharacterMatchesThresholdFilter(2)
    )
    # matchmaker = RandomMatchmaker(1)

    matchmaker = PowermatchingMatchmaker(ratings)
    generator = Generator(
        character_filter, match_filter, matchmaker, source_manager.source_versions
    )

    run = db.get_run_by_name(
        "one_piece_top_tier_16",
        source_manager,
    )

    run = Run("new_registrar_test", generator, evaluator, db, True)

    results, cost = await run.start(source_manager, AsyncLimiter(1, 6.5), verbose=True)
    # with open("results.txt", "w") as file:
    #     for result in run.results:
    #         file.write(
    #             f"{result.character_a.id} vs. {result.character_b.id}: {result.outcome}\n"
    #         )

    results = list(db.get_results())
    ratings = rate_characters(results)
    with open("ratings.txt", "w") as file:
        for character_id, rating in sorted(
            list(ratings.items()),
            key=lambda x: x[1],
        ):
            file.write(f"{character_id}: {rating}\n")


asyncio.run(main())
