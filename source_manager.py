from typing import Iterable
from character import Character
from source import Source
from config import *
import functools

from one_piece import OnePieceWiki
from marvel import MarvelWiki

available_sources: dict[str, Source] = dict(
    (source.SOURCE_ID, source) for source in [OnePieceWiki, MarvelWiki]
)


class SourceManager:
    def __init__(self, download_path: str = DOWNLOADS_FOLDER):
        self.download_path = download_path
        self.sources: dict[str, Source] = {}

    def load_source(self, source_id: str):
        if source_id not in self.sources:
            self.sources[source_id] = available_sources[source_id](self.download_path)

    @functools.lru_cache(maxsize=8192)
    def get_character(self, prefixed_character_name: str):
        source_id = prefixed_character_name.split("/")[0]
        character_name = prefixed_character_name[len(source_id) + 1 :]
        return self.sources[source_id].get_character(character_name)

    def all_characters(self) -> Iterable[Character]:
        for source in self.sources.values():
            for character_name in source.all_character_names():
                yield source.get_character(character_name)
