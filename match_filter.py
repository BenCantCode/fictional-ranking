from __future__ import annotations

from abc import abstractmethod
from character import CharacterId
from typing import Any
import json
from match import MatchResult, Outcome, PreparedMatch
from type_registrar import Type, TypeRegistrar


class MatchFilter(Type):
    TYPE_ID: str

    @abstractmethod
    def ok(
        self,
        potential_match: tuple[CharacterId, CharacterId],
        matches: list[PreparedMatch],
    ):
        raise NotImplementedError()

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        """Convert the filter's parameters (i.e. its instance variables) into a JSON-serializable dictionary."""
        pass

    @staticmethod
    @abstractmethod
    def from_parameters(
        parameters: dict[str, Any], registrar: MatchFilterTypeRegistrar
    ) -> MatchFilter:
        """Instantiate the filter by deserializing the dictionary of parameters previously serialized in the `parameters` method."""
        pass

    def to_object(self):
        """Serialize the matchmaker into a JSON-serializable object. Don't override this."""
        return {"type": self.TYPE_ID, **self.parameters}

    @staticmethod
    def from_object(
        object: dict[str, Any],
        registrar: MatchFilterTypeRegistrar,
    ) -> MatchFilter:
        """Instantiate a filter from a JSON-deserialized object. Don't override this."""
        return registrar.get_type(object["type"]).from_parameters(object, registrar)


class OrFilter(MatchFilter):
    TYPE_ID = "or"

    def __init__(self, *subfilters: MatchFilter):
        self.subfilters = list(subfilters)

    @property
    def parameters(self) -> dict[str, Any]:
        return {"subfilters": [subfilter.to_object() for subfilter in self.subfilters]}

    @staticmethod
    def from_parameters(
        parameters: dict[str, Any], registrar: MatchFilterTypeRegistrar
    ) -> MatchFilter:
        return OrFilter(
            *[
                MatchFilter.from_object(subfilter_object, registrar)
                for subfilter_object in parameters["subfilters"]
            ]
        )

    def ok(
        self,
        match: tuple[CharacterId, CharacterId],
        matches: list[PreparedMatch],
    ):
        for subfilter in self.subfilters:
            if subfilter.ok(match, matches):
                return True
        return False


class AndFilter(MatchFilter):
    TYPE_ID = "and"

    def __init__(self, *subfilters: MatchFilter):
        self.subfilters = list(subfilters)

    @property
    def parameters(self) -> dict[str, Any]:
        return {"subfilters": [subfilter.to_object() for subfilter in self.subfilters]}

    @staticmethod
    def from_parameters(
        parameters: dict[str, Any], registrar: MatchFilterTypeRegistrar
    ) -> MatchFilter:
        return AndFilter(
            *[
                MatchFilter.from_object(subfilter_object, registrar)
                for subfilter_object in parameters["subfilters"]
            ]
        )

    def ok(
        self,
        match: tuple[CharacterId, CharacterId],
        matches: list[PreparedMatch],
    ):
        for subfilter in self.subfilters:
            if not subfilter.ok(match, matches):
                return False
        return False


class InvertFilter(MatchFilter):
    TYPE_ID = "invert"

    def __init__(self, subfilter: MatchFilter):
        self.subfilter = subfilter

    @property
    def parameters(self) -> dict[str, Any]:
        return {"subfilter": self.subfilter.to_object()}

    @staticmethod
    def from_parameters(
        parameters: dict[str, Any], registrar: MatchFilterTypeRegistrar
    ) -> MatchFilter:
        return InvertFilter(MatchFilter.from_object(parameters["subfilter"], registrar))

    def ok(
        self,
        match: tuple[CharacterId, CharacterId],
        matches: list[PreparedMatch],
    ):
        return not self.subfilter.ok(match, matches)


def or_filter(a: MatchFilter, b: MatchFilter):
    if isinstance(a, OrFilter):
        a.subfilters.append(b)
        return a
    elif isinstance(b, OrFilter):
        b.subfilters.append(a)
        return b
    else:
        return OrFilter(a, b)


MatchFilter.__or__ = or_filter  # type: ignore


def and_filter(a: MatchFilter, b: MatchFilter):
    if isinstance(a, AndFilter):
        a.subfilters.append(b)
        return a
    elif isinstance(b, AndFilter):
        b.subfilters.append(a)
        return b
    else:
        return AndFilter(a, b)


MatchFilter.__and__ = and_filter  # type: ignore


def invert_filter(a: MatchFilter):
    return InvertFilter(a)


MatchFilter.__invert__ = invert_filter  # type: ignore


class DuplicateMatchInRunFilter(MatchFilter):
    TYPE_ID = "duplicate_run"

    def __init__(self, order_dependent=False):
        self.order_dependent = order_dependent

    @property
    def parameters(self) -> dict[str, Any]:
        return {"order_dependent": self.order_dependent}

    @staticmethod
    def from_parameters(
        parameters: dict[str, Any], registrar: MatchFilterTypeRegistrar
    ) -> MatchFilter:
        return DuplicateMatchInRunFilter(parameters["order_dependent"])

    def ok(
        self,
        match: tuple[CharacterId, CharacterId],
        matches: list[PreparedMatch],
    ):
        if any(
            prior_match
            for prior_match in matches
            if prior_match.character_a == match[0]
            and prior_match.character_b == match[1]
        ):
            return True
        if not self.order_dependent and any(
            prior_match
            for prior_match in matches
            if prior_match.character_b == match[0]
            and prior_match.character_a == match[1]
        ):
            return True
        return False


class DuplicateMatchInPriorRunFilter(MatchFilter):
    TYPE_ID = "duplicate_prior_run"

    def __init__(
        self,
        results: list[MatchResult],
        order_dependent: bool = False,
        ignore_unfinished: bool = True,
    ):
        # TODO: Take into account character attributes
        self.prior_matches = [
            (result.character_a.id, result.character_b.id)
            for result in results
            if ignore_unfinished
            and result.outcome not in [Outcome.A_WINS, Outcome.B_WINS]
        ]
        self.order_dependent = order_dependent
        self.ignore_unfinished = ignore_unfinished

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "order_dependent": self.order_dependent,
            "ignore_unfinished": self.ignore_unfinished,
        }

    @staticmethod
    def from_parameters(
        parameters: dict[str, Any], registrar: MatchFilterTypeRegistrar
    ) -> MatchFilter:
        # TODO: Requires results, but none can be obtained from the object alone.
        raise NotImplementedError()
        # return DuplicateMatchInPriorRunFilter(
        #     None, parameters["order_dependent"], parameters["ignore_unfinished"]
        # )

    @abstractmethod
    def ok(
        self,
        match: tuple[CharacterId, CharacterId],
        matches: list[PreparedMatch],
    ):
        if match in self.prior_matches:
            return True
        if self.order_dependent and (match[1], match[0]) in self.prior_matches:
            return True
        return False


class MatchFilterTypeRegistrar(TypeRegistrar[MatchFilter]):
    DEFAULT_TYPES: list[type[MatchFilter]] = [
        OrFilter,
        AndFilter,
        InvertFilter,
        DuplicateMatchInRunFilter,
        DuplicateMatchInPriorRunFilter,
    ]
