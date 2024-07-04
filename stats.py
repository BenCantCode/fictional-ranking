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
    MatchCharacterFilter,
)
from matchmaking import (
    MATCHMAKER_TYPE_REGISTRAR,
    PowermatchingMatchmaker,
    RandomMatchmaker,
    InvertedOrdinalizedPowermatchingMatchmaker,
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
    await source_manager.load_source("one_piece")

    evaluator = Evaluator()

    results = list(db.get_results())

    one_piece_results_filter = SourceFilter("one_piece")

    marvel_universe_filter = SourceFilter("marvel") & (
        CharacterNameFilter(re.compile("^.* \\(Earth-616\\)$"))
        | CharacterNameFilter(re.compile("^.* \\(Multiverse\\)$"))
    )

    marvel_results_filter = marvel_universe_filter

    ratings = rate_characters(
        results, source_manager, filter=one_piece_results_filter | marvel_results_filter
    )

    marvel_character_filter = marvel_universe_filter & LengthFilter(14000)

    one_piece_character_filter = SourceFilter("one_piece") & LengthFilter(8000)

    character_filter = marvel_character_filter | one_piece_character_filter

    match_filter = (
        ~SelfMatchFilter()
        & MatchCharacterFilter(SourceFilter("one_piece"), SourceFilter("marvel"))
        & ~DuplicateMatchInRunFilter()
        # & ~CharacterMatchesThresholdFilter(4)
    )

    # matchmaker = RandomMatchmaker(1)
    matchmaker = InvertedOrdinalizedPowermatchingMatchmaker(
        ratings, one_piece_character_filter, marvel_character_filter, source_manager
    )

    generator = Generator(
        character_filter, match_filter, matchmaker, source_manager.source_versions
    )

    # run = db.get_run_by_name(
    #     "marvel_powermatched_3",
    #     source_manager,
    # )

    run = Run("marvel_vs_onepiece_1", generator, evaluator, db, False)

    results, cost = await run.start(source_manager, AsyncLimiter(1, 3), verbose=True)
    with open("results.txt", "w") as file:
        for result in run.results:
            file.write(
                f"{result.character_a.id} vs. {result.character_b.id}: {result.outcome}\n"
            )
    print(len(results), "Total Matches")

    results = list(db.get_results())
    ratings = rate_characters(results, source_manager, filter=EverythingFilter())
    with open("ratings.txt", "w") as file:
        for character_id, rating in sorted(
            list(ratings.items()),
            key=lambda x: x[1],
        ):
            file.write(f"{character_id}: {rating}\n")


asyncio.run(main())
