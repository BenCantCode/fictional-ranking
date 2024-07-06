from aiolimiter import AsyncLimiter
from jinja2 import Template
from math import ceil, inf
from os.path import join, dirname
from character import CharacterId
from db import RunsDatabase
from exceptions import NotACharacterException
from rating import rate_characters
from source_manager import SourceManager
from character_filter import EverythingFilter, SourceFilter, LengthFilter
import asyncio

USE_SOURCES = ["one_piece", "marvel"]
CHARACTER_FILTER = EverythingFilter()
RATINGS_FILTER = EverythingFilter()

DEFAULT_TIERS = ["S", "A", "B", "C", "D", "E", "F"]
MAX_TIER_RATING_RANGE = 400

MAX_IMAGE_WIDTH = 350
MAX_IMAGE_HEIGHT = None


def rating_to_grade(rating: float, grades: dict[str, float]) -> str:
    for grade, cutoff in reversed(grades.items()):
        if cutoff <= rating:
            return grade
    raise ValueError()


def generate_grade_cutoffs(ratings: dict[CharacterId, float]):
    min_rating = min(ratings.values())
    max_rating = max(ratings.values())
    print(min_rating, max_rating)
    rating_range = max_rating - min_rating
    min_num_tiers = max(ceil(rating_range / MAX_TIER_RATING_RANGE), len(DEFAULT_TIERS))
    extra_tiers_per_default_tier: int = (
        ceil(((min_num_tiers - len(DEFAULT_TIERS)) / len(DEFAULT_TIERS)) / 2) * 2
    )
    num_tiers = len(DEFAULT_TIERS) * (1 + extra_tiers_per_default_tier)
    tier_rating_range = rating_range / num_tiers
    tiers = {}
    tier_rating = min_rating
    for default_tier in reversed(DEFAULT_TIERS):
        sub_tiers = (
            [
                default_tier + ("-" * i)
                for i in range(extra_tiers_per_default_tier // 2, 0, -1)
            ]
            + [default_tier]
            + [
                default_tier + ("+" * i)
                for i in range(1, extra_tiers_per_default_tier // 2 + 1, 1)
            ]
        )
        for sub_tier in sub_tiers:
            tiers[sub_tier] = tier_rating
            tier_rating += tier_rating_range
    print(tiers)
    return tiers


async def main():
    with open(join(dirname(__name__), "template.html")) as template_file:
        template = Template(template_file.read())

    source_manager = SourceManager()
    for source_id in USE_SOURCES:
        await source_manager.load_source(source_id)

    ratings = rate_characters(
        list(RunsDatabase().get_results()),
        source_manager=source_manager,
        filter=RATINGS_FILTER,
    )

    filtered_ratings = {
        id: rating
        for id, rating in ratings.items()
        if CHARACTER_FILTER.ok(id, source_manager)
    }

    grades = generate_grade_cutoffs(filtered_ratings)
    tiers = dict((grade, []) for grade in grades.keys())

    sorted_ratings = sorted(list(ratings.items()), key=lambda r: r[1], reverse=True)

    for character_id, rating in sorted_ratings:
        try:
            character = source_manager.get_character(character_id, meta_only=True)
            grade = rating_to_grade(rating, grades)
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
