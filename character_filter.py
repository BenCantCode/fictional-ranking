from __future__ import annotations

from typing import Any, TYPE_CHECKING
import json
from abc import abstractmethod
from type_registrar import Type, TypeRegistrar
import re

if TYPE_CHECKING:
    from character import CharacterId
    from source_manager import SourceManager


class CharacterFilter(Type):
    TYPE_ID: str

    @abstractmethod
    def ok(self, character_id: CharacterId, source_manager: SourceManager):
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
        registrar: CharacterFilterTypeRegistrar,
    ) -> CharacterFilter:
        """Instantiate the filter by deserializing the dictionary of parameters previously serialized in the `parameters` method."""
        raise NotImplementedError()

    def to_object(self):
        """Serialize the filter into a JSON-serializable object. Don't override this."""
        return {"type": self.TYPE_ID, **self.parameters}

    @staticmethod
    def from_object(
        object: dict[str, Any],
        registrar: CharacterFilterTypeRegistrar,
    ) -> CharacterFilter:
        """Instantiate a filter from a JSON-deserialized object. Don't override this."""
        filter_type = registrar.get_type(object["type"])
        if filter_type:
            return filter_type.from_parameters(object, registrar)
        else:
            raise ValueError()


class OrFilter(CharacterFilter):
    TYPE_ID = "or"

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
        parameters: dict[str, Any], registrar: CharacterFilterTypeRegistrar
    ) -> CharacterFilter:
        return OrFilter(
            *[
                CharacterFilter.from_object(subfilter_object, registrar)
                for subfilter_object in parameters["subfilters"]
            ]
        )


class AndFilter(CharacterFilter):
    TYPE_ID = "and"

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
        parameters: dict[str, Any], registrar: CharacterFilterTypeRegistrar
    ) -> CharacterFilter:
        return OrFilter(
            *[
                CharacterFilter.from_object(subfilter_object, registrar)
                for subfilter_object in parameters["subfilters"]
            ]
        )


class InvertFilter(CharacterFilter):
    TYPE_ID = "invert"

    def __init__(self, subfilter: CharacterFilter):
        self.subfilter = subfilter

    def ok(self, character_id: CharacterId, source_manager: SourceManager):
        return not self.subfilter.ok(character_id, source_manager)

    @property
    def parameters(self) -> dict[str, Any]:
        return {"subfilter": self.subfilter.to_object()}

    @staticmethod
    def from_parameters(
        parameters: dict[str, Any], registrar: CharacterFilterTypeRegistrar
    ) -> CharacterFilter:
        return InvertFilter(
            CharacterFilter.from_object(parameters["subfilter"], registrar)
        )


def or_filter(a: CharacterFilter, b: CharacterFilter):
    if isinstance(a, OrFilter):
        a.subfilters.append(b)
        return a
    elif isinstance(b, OrFilter):
        b.subfilters.append(a)
        return b
    else:
        return OrFilter(a, b)


CharacterFilter.__or__ = or_filter  # type: ignore


def and_filter(a: CharacterFilter, b: CharacterFilter):
    if isinstance(a, AndFilter):
        a.subfilters.append(b)
        return a
    elif isinstance(b, AndFilter):
        b.subfilters.append(a)
        return b
    else:
        return AndFilter(a, b)


CharacterFilter.__and__ = and_filter  # type: ignore


def invert_filter(a: CharacterFilter):
    return InvertFilter(a)


CharacterFilter.__invert__ = invert_filter  # type: ignore


class CharacterIdFilter(CharacterFilter):
    """Matches specific characters."""

    TYPE_ID = "character_id"

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
        parameters: dict[str, Any], registrar: CharacterFilterTypeRegistrar
    ) -> CharacterIdFilter:
        return CharacterIdFilter(parameters["characters"])


class CharacterNameFilter(CharacterFilter):
    """Matches a characters name if a provided regex matches their entire name."""

    TYPE_ID = "character_name"

    def __init__(self, pattern: re.Pattern):
        self.pattern = pattern

    def ok(self, character_id: CharacterId):
        return self.pattern.fullmatch(character_id.name)

    @property
    def parameters(self):
        return {"pattern": str(self.pattern)}

    @staticmethod
    def from_parameters(
        parameters: dict[str, Any], registrar: CharacterFilterTypeRegistrar
    ) -> CharacterNameFilter:
        return CharacterNameFilter(re.compile(parameters["pattern"]))


class SourceFilter(CharacterFilter):
    """Matches characters from specific sources."""

    TYPE_ID = "source"

    source_ids: list[str]

    def __init__(self, source_ids: list[str] = []):
        self.source_ids = source_ids

    def ok(self, character_id: CharacterId, source_manager: SourceManager):
        return character_id.source_id in self.source_ids

    @property
    def parameters(self):
        return {"sources": self.source_ids}

    @staticmethod
    def from_parameters(parameters: dict[str, Any]) -> SourceFilter:
        return SourceFilter(parameters["sources"])


class EverythingFilter(CharacterFilter):
    """Matches everything."""

    TYPE_ID = "everything"

    def ok(self, character_id: CharacterId, source_manager: SourceManager):
        return True

    @property
    def parameters(self):
        return {}

    @staticmethod
    def from_parameters(
        parameters: dict[str, Any],
        registrar: CharacterFilterTypeRegistrar,
    ) -> EverythingFilter:
        return EverythingFilter()


class CharacterFilterTypeRegistrar(TypeRegistrar[CharacterFilter]):
    DEFAULT_TYPES: list[type[CharacterFilter]] = [
        AndFilter,
        OrFilter,
        InvertFilter,
        CharacterFilter,
        SourceFilter,
        CharacterNameFilter,
        EverythingFilter,
    ]
