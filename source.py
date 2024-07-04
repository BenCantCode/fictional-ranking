from abc import ABC, abstractmethod
from os.path import exists, join
from os import makedirs

from aiolimiter import AsyncLimiter
from httpx import AsyncClient
from character import Character, CharacterId
from typing import Iterable, TYPE_CHECKING
from config import ASYNC_CLIENT, DOWNLOADS_FOLDER
from utils import copying_cache


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
    def get_character(self, character_name: str, meta_only=False) -> Character:
        pass

    def get_character_length_estimate(self, character_name: str) -> int:
        sections = self.get_character(character_name).sections
        if sections is None:
            raise ValueError("Character was initialized without sections.")
        return sum(len(section.text) for section in sections)

    @abstractmethod
    def _all_character_names(self) -> Iterable[str]:
        pass

    @copying_cache
    def all_character_names(self) -> list[str]:
        return list(self._all_character_names())

    def all_character_ids(self) -> Iterable[CharacterId]:
        for character_name in self._all_character_names():
            yield CharacterId(self.SOURCE_ID, character_name)

    def all_characters(self, meta_only: bool = False) -> Iterable[Character]:
        for character_name in self.all_character_names():
            yield self.get_character(character_name, meta_only=meta_only)
