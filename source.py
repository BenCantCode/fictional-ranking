from abc import ABC, abstractmethod
from os.path import exists, join
from os import makedirs
from character import Character
from typing import Iterable
from config import *


class Source(ABC):
    @property
    @abstractmethod
    def SOURCE_ID():
        pass

    def __init__(self, downloads_folder: str = DOWNLOADS_FOLDER):
        self.path = join(downloads_folder, self.SOURCE_ID)
        self.parsed = False
        self.load()

    @abstractmethod
    def download(self):
        pass

    def parse(self):
        self.parsed = True

    def load(self):
        if not exists(self.path):
            self.download()
        self.parse()

    @abstractmethod
    def get_character(self, character_name: str) -> Character:
        pass

    @abstractmethod
    def all_characters(self) -> Iterable[Character]:
        pass

    def all_character_names(self) -> Iterable[str]:
        for character in self.all_characters():
            yield character.name

    def all_character_ids(self) -> Iterable[str]:
        return (f"{self.SOURCE_ID}/{name}" for name in self.all_character_names())
