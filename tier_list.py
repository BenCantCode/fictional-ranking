from aiolimiter import AsyncLimiter
from jinja2 import Template
from math import inf
from os.path import join, dirname
from character import CharacterId
from db import RunsDatabase
from rating import rate_characters
from source_manager import SourceManager
import asyncio

DEFAULT_CUTOFFS = {
    6000: "S",
    5000: "A",
    2000: "B",
    0: "C",
    -2000: "D",
    -3000: "E",
    -inf: "F",
}


def rating_to_grade(rating: float) -> str:
    for cutoff, grade in DEFAULT_CUTOFFS.items():
        if cutoff < rating:
            return grade
    raise ValueError()


async def main():
    with open(join(dirname(__name__), "template.html")) as template_file:
        template = Template(template_file.read())

    manager = SourceManager()
    await manager.load_source("one_piece")

    ratings = rate_characters(list(RunsDatabase().get_results()))

    rate_limit = AsyncLimiter(1, 2)

    tiers = dict((grade, []) for grade in DEFAULT_CUTOFFS.values())

    sorted_ratings = sorted(list(ratings.items()), key=lambda r: r[1], reverse=True)

    for character_id, rating in sorted_ratings:
        print(character_id)
        character = manager.get_character(character_id)
        print("got character")
        image = await character.get_image(rate_limit, download_if_unavailable=False)
        print("got image")
        image_url = None
        if image != None:
            image_url = "file://" + image
        name = character_id.name
        grade = rating_to_grade(rating)
        tiers[grade].append({"name": name, "image": image_url})

    with open("result.html", "w") as result_file:
        result_file.write(template.render(tiers=tiers))


asyncio.run(main())
