import asyncio
from one_piece import OnePieceWiki
from aiolimiter import AsyncLimiter


async def main():
    wiki = OnePieceWiki()
    await wiki.load()
    limiter = AsyncLimiter(1, 1)
    result = await wiki.get_character("Nami").get_image(limiter)
    print(result)


asyncio.run(main())
