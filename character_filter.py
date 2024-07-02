from __future__ import annotations

from typing import Any, TYPE_CHECKING
import json
from abc import abstractmethod
from character import CharacterId
from type_registrar import Type, TypeRegistrar
import re

if TYPE_CHECKING:
    from character import CharacterId
    from source_manager import SourceManager

CHARACTER_FILTER_TYPE_REGISTRAR = TypeRegistrar["CharacterFilter"]()


class CharacterFilter(Type):
    @abstractmethod
    def ok(self, character_id: CharacterId, source_manager: SourceManager) -> bool:
        raise NotImplementedError()

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        """Convert the filter's parameters (i.e. its instance variables) into a JSON-serializable dictionary."""
        pass

    @staticmethod
    @abstractmethod
    def from_parameters(
        parameters: dict[str, Any],
        registrar: TypeRegistrar[CharacterFilter],
    ) -> CharacterFilter:
        """Instantiate the filter by deserializing the dictionary of parameters previously serialized in the `parameters` method."""
        raise NotImplementedError()

    def to_object(self):
        """Serialize the filter into a JSON-serializable object. Don't override this."""
        return {"type": self.TYPE_ID, **self.parameters}

    @staticmethod
    def from_object(
        object: dict[str, Any],
        registrar: TypeRegistrar[CharacterFilter],
    ) -> CharacterFilter:
        """Instantiate a filter from a JSON-deserialized object. Don't override this."""
        filter_type = registrar.get_type(object["type"])
        if filter_type:
            return filter_type.from_parameters(object, registrar)
        else:
            raise ValueError()

    # Shims for type checker
    def __and__(self, other) -> CharacterFilter:
        raise NotImplementedError()

    def __or__(self, other) -> CharacterFilter:
        raise NotImplementedError()

    def __invert__(self) -> CharacterFilter:
        raise NotImplementedError()


@CHARACTER_FILTER_TYPE_REGISTRAR.register("or")
class OrFilter(CharacterFilter):
    def __init__(self, *subfilters: CharacterFilter):
        self.subfilters = list(subfilters)

    def ok(self, character_id: CharacterId, source_manager: SourceManager):
        for subfilter in self.subfilters:
            if subfilter.ok(character_id, source_manager):
                return True
        return False

    @property
    def parameters(self) -> dict[str, Any]:
        return {"subfilters": [subfilter.to_object() for subfilter in self.subfilters]}

    @staticmethod
    def from_parameters(
        parameters: dict[str, Any], registrar: TypeRegistrar[CharacterFilter]
    ) -> OrFilter:
        return OrFilter(
            *[
                CharacterFilter.from_object(subfilter_object, registrar)
                for subfilter_object in parameters["subfilters"]
            ]
        )


@CHARACTER_FILTER_TYPE_REGISTRAR.register("and")
class AndFilter(CharacterFilter):

    def __init__(self, *subfilters: CharacterFilter):
        self.subfilters = list(subfilters)

    def ok(self, character_id: CharacterId, source_manager: SourceManager):
        for subfilter in self.subfilters:
            if not subfilter.ok(character_id, source_manager):
                return False
        return True

    @property
    def parameters(self) -> dict[str, Any]:
        return {"subfilters": [subfilter.to_object() for subfilter in self.subfilters]}

    @staticmethod
    def from_parameters(
        parameters: dict[str, Any], registrar: TypeRegistrar[CharacterFilter]
    ) -> AndFilter:
        return AndFilter(
            *[
                CharacterFilter.from_object(subfilter_object, registrar)
                for subfilter_object in parameters["subfilters"]
            ]
        )


@CHARACTER_FILTER_TYPE_REGISTRAR.register("invert")
class InvertFilter(CharacterFilter):
    def __init__(self, subfilter: CharacterFilter):
        self.subfilter = subfilter

    def ok(self, character_id: CharacterId, source_manager: SourceManager):
        return not self.subfilter.ok(character_id, source_manager)

    @property
    def parameters(self) -> dict[str, Any]:
        return {"subfilter": self.subfilter.to_object()}

    @staticmethod
    def from_parameters(
        parameters: dict[str, Any], registrar: TypeRegistrar[CharacterFilter]
    ) -> InvertFilter:
        return InvertFilter(
            CharacterFilter.from_object(parameters["subfilter"], registrar)
        )


def _or_filter(a, b) -> OrFilter:
    if isinstance(a, OrFilter):
        a.subfilters.append(b)
        return a
    elif isinstance(b, OrFilter):
        b.subfilters.append(a)
        return b
    else:
        return OrFilter(a, b)


CharacterFilter.__or__ = _or_filter  # type: ignore


def _and_filter(a, b):
    if isinstance(a, AndFilter):
        a.subfilters.append(b)
        return a
    elif isinstance(b, AndFilter):
        b.subfilters.append(a)
        return b
    else:
        return AndFilter(a, b)


CharacterFilter.__and__ = _and_filter  # type: ignore


def invert_filter(a: CharacterFilter):
    return InvertFilter(a)


CharacterFilter.__invert__ = invert_filter  # type: ignore


@CHARACTER_FILTER_TYPE_REGISTRAR.register("character_id")
class CharacterIdFilter(CharacterFilter):
    """Matches specific characters."""

    def __init__(self, character_ids: list[CharacterId]):
        self.character_ids = character_ids
        self.possible_sources = [
            character_id.source_id for character_id in character_ids
        ]

    def ok(self, character_id: CharacterId, source_manager: SourceManager):
        return character_id in self.character_ids

    @property
    def parameters(self):
        return {"characters": [str(id) for id in self.character_ids]}

    @staticmethod
    def from_parameters(
        parameters: dict[str, Any], registrar: TypeRegistrar[CharacterFilter]
    ) -> CharacterIdFilter:
        return CharacterIdFilter(
            [CharacterId.from_str(id) for id in parameters["characters"]]
        )


@CHARACTER_FILTER_TYPE_REGISTRAR.register("character_name")
class CharacterNameFilter(CharacterFilter):
    """Matches a characters name if a provided regex matches their entire name."""

    def __init__(self, pattern: re.Pattern):
        self.pattern = pattern

    def ok(self, character_id: CharacterId, source_manager: SourceManager):
        return self.pattern.fullmatch(character_id.name)

    @property
    def parameters(self):
        return {"pattern": str(self.pattern)}

    @staticmethod
    def from_parameters(
        parameters: dict[str, Any], registrar: TypeRegistrar[CharacterFilter]
    ) -> CharacterNameFilter:
        return CharacterNameFilter(re.compile(parameters["pattern"]))


@CHARACTER_FILTER_TYPE_REGISTRAR.register("source")
class SourceFilter(CharacterFilter):
    """Matches characters from specific sources."""

    source_ids: list[str]

    def __init__(self, source_ids: list[str] = []):
        self.source_ids = source_ids

    def ok(self, character_id: CharacterId, source_manager: SourceManager):
        return character_id.source_id in self.source_ids

    @property
    def parameters(self):
        return {"sources": self.source_ids}

    @staticmethod
    def from_parameters(
        parameters: dict[str, Any], registrar: TypeRegistrar[CharacterFilter]
    ) -> SourceFilter:
        return SourceFilter(parameters["sources"])


@CHARACTER_FILTER_TYPE_REGISTRAR.register("everything")
class EverythingFilter(CharacterFilter):
    """Matches everything."""

    def ok(self, character_id: CharacterId, source_manager: SourceManager):
        return True

    @property
    def parameters(self):
        return {}

    @staticmethod
    def from_parameters(
        parameters: dict[str, Any],
        registrar: TypeRegistrar[CharacterFilter],
    ) -> EverythingFilter:
        return EverythingFilter()


@CHARACTER_FILTER_TYPE_REGISTRAR.register("rating")
class RatingFilter(CharacterFilter):
    """Matches characters based on their rating."""

    def __init__(self, threshold: float, ratings: dict[CharacterId, float]):
        self.threshold = threshold
        self.valid_ids = [
            character_id
            for (character_id, rating) in ratings.items()
            if rating >= threshold
        ]

    def ok(self, character_id: CharacterId, source_manager: SourceManager):
        return character_id in self.valid_ids

    @property
    def parameters(self):
        return {"threshold": self.threshold}

    @staticmethod
    def from_parameters(
        parameters: dict[str, Any],
        registrar: TypeRegistrar[CharacterFilter],
    ):
        raise NotImplementedError("Cannot construct a RatingFilter without ratings.")


@CHARACTER_FILTER_TYPE_REGISTRAR.register("length")
class LengthFilter(CharacterFilter):
    """Matches characters based on their abridged article length."""

    def __init__(self, threshold: float):
        self.threshold = threshold

    def ok(self, character_id: CharacterId, source_manager: SourceManager):
        # Hopefully this is cached.
        return (
            source_manager.get_character_length_estimate(character_id) >= self.threshold
        )

    @property
    def parameters(self):
        return {"threshold": self.threshold}

    @staticmethod
    def from_parameters(
        parameters: dict[str, Any],
        registrar: TypeRegistrar[CharacterFilter],
    ):
        raise NotImplementedError("Cannot construct a RatingFilter without ratings.")
