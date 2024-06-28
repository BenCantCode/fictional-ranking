from __future__ import annotations
from typing import Any, TYPE_CHECKING, Iterable
from match import PreparedMatch
from source_manager import SourceManager
from character import CharacterId
from character_filter import CharacterFilter, CharacterFilterTypeRegistrar
from match_filter import MatchFilter, MatchFilterTypeRegistrar
from matchmaking import Matchmaker, MatchmakerTypeRegistrar

if TYPE_CHECKING:
    from run import Run
    from db import RunsDatabase


class Generator:
    def __init__(
        self,
        character_filter: CharacterFilter,
        match_filter: MatchFilter,
        matchmaker: Matchmaker,
        source_versions: dict[str, str | None],
    ):
        self.character_filter = character_filter
        self.match_filter = match_filter
        self.matchmaker = matchmaker
        self.source_versions = source_versions

    @staticmethod
    def from_object(
        object: dict[str, Any],
        character_filter_type_registrar: CharacterFilterTypeRegistrar,
        matchmaker_type_registrar: MatchmakerTypeRegistrar,
        match_filter_type_registrar: MatchFilterTypeRegistrar,
    ):
        return Generator(
            CharacterFilter.from_object(
                object["character_filters"], character_filter_type_registrar
            ),
            MatchFilter.from_object(
                object["match_filter"], match_filter_type_registrar
            ),
            Matchmaker.from_object(object["matchmaker"], matchmaker_type_registrar),
            object["source_versions"],
        )

    def to_object(self):
        return {
            "character_filters": self.character_filter.to_object(),
            "match_filter": self.match_filter.to_object(),
            "matchmaker": self.matchmaker.to_object(),
            "source_versions": self.source_versions,
        }

    def generate_matches(
        self, run: Run, source_manager: SourceManager, db: RunsDatabase | None
    ) -> Iterable[PreparedMatch]:
        character_ids_set: set[CharacterId] = set()
        for potential_character_id in source_manager.all_character_ids():
            if self.character_filter.ok(potential_character_id, source_manager):
                character_ids_set.add(potential_character_id)
        character_ids_list: list[CharacterId] = list(character_ids_set)
        matches = []
        for (
            character_a_id,
            character_b_id,
        ) in self.matchmaker.generate_matches(
            character_ids_list, self.match_filter, matches
        ):
            character_a = source_manager.get_character(character_a_id)
            character_b = source_manager.get_character(character_b_id)
            match = PreparedMatch(
                run.run_id,
                character_a,
                character_b,
                db,
            )
            yield match
            matches.append(match)
