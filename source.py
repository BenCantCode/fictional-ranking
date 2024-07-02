from abc import ABC, abstractmethod
from os.path import exists, join
from os import makedirs

from aiolimiter import AsyncLimiter
from httpx import AsyncClient
from character import Character, CharacterId
from typing import Iterable, TYPE_CHECKING
from config import ASYNC_CLIENT, DOWNLOADS_FOLDER


class Source(ABC):
    SOURCE_ID: str
    version: str | None = None

    if not TYPE_CHECKING:

        @property
        @abstractmethod
        def SOURCE_ID():
            pass

    def __init__(
        self,
        downloads_folder: str = DOWNLOADS_FOLDER,
    ):
        self.path = join(downloads_folder, self.SOURCE_ID)
        self.parsed = False

    @property
    def downloaded(self) -> bool:
        return exists(self.path)

    @abstractmethod
    async def download(self):
        pass

    @abstractmethod
    def parse(self):
        pass

    async def load(self):
        if not self.parsed:
            if not self.downloaded:
                await self.download()
            self.parse()

    @abstractmethod
    def get_character(self, character_name: str) -> Character:
        pass

    def get_character_length_estimate(self, character_name: str) -> int:
        return sum(
            len(section.text) for section in self.get_character(character_name).sections
        )

    async def get_image(
        self,
        character: Character,
        rate_limit: AsyncLimiter,
        async_client: AsyncClient = ASYNC_CLIENT,
        download_if_unavailable: bool = True,
    ) -> str | None:
        return None

    @abstractmethod
    def all_characters(self) -> Iterable[Character]:
        pass

    def all_character_names(self) -> Iterable[str]:
        for character in self.all_characters():
            yield character.id.name

    def all_character_ids(self) -> Iterable[CharacterId]:
        for character_name in self.all_character_names():
            yield CharacterId(self.SOURCE_ID, character_name)
