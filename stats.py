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
    CharacterNameFilter,
    LengthFilter,
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
import re

logging.basicConfig(level=logging.INFO)
logging.getLogger("LiteLLM").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("LiteLLM Router").setLevel(logging.WARNING)


async def main():
    db = RunsDatabase()
    source_manager = SourceManager()
    await source_manager.load_source("marvel")

    evaluator = Evaluator()

    results = list(db.get_results())

    character_filter = (
        SourceFilter("marvel")
        & (
            CharacterNameFilter(re.compile("^.* \\(Earth-616\\)$"))
            | CharacterNameFilter(re.compile("^.* \\(Multiverse\\)$"))
        )
        & LengthFilter(10000)
    )
    match_filter = (
        ~SelfMatchFilter()
        & ~DuplicateMatchInRunFilter()
        & ~DuplicateMatchInPriorRunFilter(results, threshold=1)
        & ~CharacterMatchesThresholdFilter(2)
    )

    ratings = rate_characters(results, source_manager, filter=character_filter)

    # matchmaker = RandomMatchmaker(1)
    matchmaker = PowermatchingMatchmaker(ratings)
    generator = Generator(
        character_filter, match_filter, matchmaker, source_manager.source_versions
    )

    # run = db.get_run_by_name(
    #     "marvel_random_1",
    #     source_manager,
    # )

    run = Run("marvel_powermatched_1", generator, evaluator, db, False)

    results, cost = await run.start(source_manager, AsyncLimiter(1, 3), verbose=True)
    with open("results.txt", "w") as file:
        for result in run.results:
            file.write(
                f"{result.character_a.id} vs. {result.character_b.id}: {result.outcome}\n"
            )

    results = list(db.get_results())
    ratings = rate_characters(results, source_manager, filter=character_filter)
    with open("ratings.txt", "w") as file:
        for character_id, rating in sorted(
            list(ratings.items()),
            key=lambda x: x[1],
        ):
            file.write(f"{character_id}: {rating}\n")


asyncio.run(main())
