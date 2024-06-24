from __future__ import annotations
from abc import abstractmethod
from character import CharacterId
from random import Random, getrandbits
from typing import Iterable, Any
from match import PreparedMatch
from match_filter import MatchFilter
from type_registrar import Type, TypeRegistrar
import json


class Matchmaker(Type):
    TYPE_ID: str

    @abstractmethod
    def generate_matches(
        self,
        characters: list[CharacterId],
        match_filter: MatchFilter,
        matches: list[PreparedMatch],
    ) -> Iterable[tuple[CharacterId, CharacterId]]:
        raise NotImplementedError()

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        raise NotImplementedError()

    def to_object(self):
        """Serialize the matchmaker into a JSON-serializable object. Don't override this."""
        return {"type": self.TYPE_ID, **self.parameters}

    @staticmethod
    def from_object(
        object: dict[str, Any],
        registrar: MatchmakerTypeRegistrar,
    ) -> Matchmaker:
        """Instantiate a filter from a JSON-deserialized object. Don't override this."""
        return registrar.get_type(object["type"]).from_parameters(object, registrar)

    @staticmethod
    @abstractmethod
    def from_parameters(
        parameters: dict[str, Any], registrar: MatchmakerTypeRegistrar
    ) -> Matchmaker:
        raise NotImplementedError()


class RandomMatchmaker(Matchmaker):
    TYPE_ID = "random"

    def __init__(self, seed: int | None = None):
        if seed == None:
            seed = getrandbits(32)
        self.seed = seed

    def generate_matches(
        self,
        character_ids: list[CharacterId],
        filter: MatchFilter,
        matches: list[PreparedMatch],
    ) -> Iterable[tuple[CharacterId, CharacterId]]:
        random = Random(self.seed)
        for character_id in character_ids:
            while True:
                opponent_id = character_ids[random.randint(0, len(character_ids) - 1)]
                match = (character_id, opponent_id)
                if filter.ok(match, matches):
                    yield match
                    break

    @staticmethod
    def from_parameters(
        parameters: dict[str, Any], registrar: MatchmakerTypeRegistrar
    ) -> Matchmaker:
        return RandomMatchmaker(parameters["seed"])

    @property
    def parameters(self) -> dict[str, Any]:
        return {"seed": self.seed}


class PowermatchingMatchmaker(Matchmaker):
    TYPE_ID = "powermatched"

    def __init__(self, ratings: dict[CharacterId, float]):
        self.ratings = ratings

    def generate_matches(
        self,
        character_ids: list[CharacterId],
        filter: MatchFilter,
        matches: list[PreparedMatch],
    ) -> Iterable[tuple[CharacterId, CharacterId]]:
        for character_id in character_ids:
            rating = self.ratings[character_id]
            distances = sorted(
                character_ids,
                key=lambda opponent_id: abs(rating - self.ratings[opponent_id]),
            )
            distances.remove(character_id)
            for opponent_id in distances:
                match = (character_id, opponent_id)
                if filter.ok(match, matches):
                    yield match
                    break

    @staticmethod
    def from_parameters(
        parameters: dict[str, Any], registrar: MatchmakerTypeRegistrar
    ) -> Matchmaker:
        raise NotImplementedError()

    @property
    def parameters(self) -> dict[str, Any]:
        return {}


class MatchmakerTypeRegistrar(TypeRegistrar[Matchmaker]):
    DEFAULT_TYPES: list[type[Matchmaker]] = [RandomMatchmaker, PowermatchingMatchmaker]
