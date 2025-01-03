from typing import Iterable
from character import Character, CharacterId
from source import Source
from config import *
import functools

from one_piece import OnePieceWiki
from marvel import MarvelWiki

AVAILABLE_SOURCES: dict[str, type[Source]] = dict(
    (source.SOURCE_ID, source) for source in [OnePieceWiki, MarvelWiki]
)


class SourceManager:
    def __init__(self, download_path: str = DOWNLOADS_FOLDER):
        self.download_path = download_path
        self.sources: dict[str, Source] = {}

    async def load_source(self, source_id: str):
        if source_id not in self.sources:
            source = AVAILABLE_SOURCES[source_id](self.download_path)
            self.sources[source_id] = source
            await source.load()
            return source
        else:
            return self.sources[source_id]

    @functools.lru_cache(maxsize=8192)
    def get_character(self, character_id: CharacterId, meta_only=False):
        return self.sources[character_id.source_id].get_character(
            character_id.name, meta_only=meta_only
        )

    def get_character_length_estimate(self, character_id: CharacterId):
        return self.sources[character_id.source_id].get_character_length_estimate(
            character_id.name
        )

    def all_characters(self) -> Iterable[Character]:
        for source in self.sources.values():
            for character_name in source.all_character_names():
                yield source.get_character(character_name)

    def all_character_ids(self) -> Iterable[CharacterId]:
        for source in self.sources.values():
            for character_id in source.all_character_ids():
                yield character_id

    @property
    def source_versions(self) -> dict[str, str | None]:
        return dict(
            (source.SOURCE_ID, source.version) for source in self.sources.values()
        )
