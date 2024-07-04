from aiolimiter import AsyncLimiter
from jinja2 import Template
from math import inf
from os.path import join, dirname
from character import CharacterId
from db import RunsDatabase
from exceptions import NotACharacterException
from rating import rate_characters
from source_manager import SourceManager
from character_filter import EverythingFilter, SourceFilter
import asyncio

USE_SOURCES = ["one_piece", "marvel"]

CHARACTER_FILTER = SourceFilter(*USE_SOURCES)

# Group of 800 elo (~99% win probability) centered around 1600.
DEFAULT_CUTOFFS = {
    3600: "S",
    2800: "A",
    2000: "B",
    1200: "C",
    400: "D",
    -400: "E",
    -inf: "F",
}

MAX_IMAGE_WIDTH = 512
MAX_IMAGE_HEIGHT = 512


def rating_to_grade(rating: float) -> str:
    for cutoff, grade in DEFAULT_CUTOFFS.items():
        if cutoff < rating:
            return grade
    raise ValueError()


async def main():
    with open(join(dirname(__name__), "template.html")) as template_file:
        template = Template(template_file.read())

    source_manager = SourceManager()
    for source_id in USE_SOURCES:
        await source_manager.load_source(source_id)

    ratings = rate_characters(
        list(RunsDatabase().get_results()),
        source_manager=source_manager,
        filter=CHARACTER_FILTER,
    )

    tiers = dict((grade, []) for grade in DEFAULT_CUTOFFS.values())

    sorted_ratings = sorted(list(ratings.items()), key=lambda r: r[1], reverse=True)

    for character_id, rating in sorted_ratings:
        try:
            character = source_manager.get_character(character_id, meta_only=True)
            grade = rating_to_grade(rating)
            tiers[grade].append(character)
        except NotACharacterException:
            pass

    with open("result.html", "w") as result_file:
        result_file.write(
            template.render(
                tiers=tiers,
                max_image_width=MAX_IMAGE_WIDTH,
                max_image_height=MAX_IMAGE_HEIGHT,
            )
        )


asyncio.run(main())
