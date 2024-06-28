from __future__ import annotations

from abc import abstractmethod
from character import CharacterId
from typing import Any
import json
from match import MatchResult, Outcome, PreparedMatch
from type_registrar import Type, TypeRegistrar


MATCH_FILTER_TYPE_REGISTRAR = TypeRegistrar["MatchFilter"]()


class MatchFilter(Type):
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
        parameters: dict[str, Any], registrar: TypeRegistrar[MatchFilter]
    ) -> MatchFilter:
        """Instantiate the filter by deserializing the dictionary of parameters previously serialized in the `parameters` method."""
        pass

    def to_object(self):
        """Serialize the matchmaker into a JSON-serializable object. Don't override this."""
        return {"type": self.TYPE_ID, **self.parameters}

    @staticmethod
    def from_object(
        object: dict[str, Any],
        registrar: TypeRegistrar[MatchFilter],
    ) -> MatchFilter:
        """Instantiate a filter from a JSON-deserialized object. Don't override this."""
        return registrar.get_type(object["type"]).from_parameters(object, registrar)

    # Shims for type checker
    def __and__(self, other):
        raise NotImplementedError()

    def __or__(self, other):
        raise NotImplementedError()

    def __invert__(self):
        raise NotImplementedError()


@MATCH_FILTER_TYPE_REGISTRAR.register("or")
class OrFilter(MatchFilter):
    def __init__(self, *subfilters: MatchFilter):
        self.subfilters = list(subfilters)

    @property
    def parameters(self) -> dict[str, Any]:
        return {"subfilters": [subfilter.to_object() for subfilter in self.subfilters]}

    @staticmethod
    def from_parameters(
        parameters: dict[str, Any], registrar: TypeRegistrar[MatchFilter]
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


@MATCH_FILTER_TYPE_REGISTRAR.register("and")
class AndFilter(MatchFilter):
    def __init__(self, *subfilters: MatchFilter):
        self.subfilters = list(subfilters)

    @property
    def parameters(self) -> dict[str, Any]:
        return {"subfilters": [subfilter.to_object() for subfilter in self.subfilters]}

    @staticmethod
    def from_parameters(
        parameters: dict[str, Any], registrar: TypeRegistrar[MatchFilter]
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
        return True


@MATCH_FILTER_TYPE_REGISTRAR.register("invert")
class InvertFilter(MatchFilter):
    def __init__(self, subfilter: MatchFilter):
        self.subfilter = subfilter

    @property
    def parameters(self) -> dict[str, Any]:
        return {"subfilter": self.subfilter.to_object()}

    @staticmethod
    def from_parameters(
        parameters: dict[str, Any], registrar: TypeRegistrar[MatchFilter]
    ) -> MatchFilter:
        return InvertFilter(MatchFilter.from_object(parameters["subfilter"], registrar))

    def ok(
        self,
        match: tuple[CharacterId, CharacterId],
        matches: list[PreparedMatch],
    ):
        return not self.subfilter.ok(match, matches)


def or_filter(a, b):
    if isinstance(a, OrFilter):
        a.subfilters.append(b)
        return a
    elif isinstance(b, OrFilter):
        b.subfilters.append(a)
        return b
    else:
        return OrFilter(a, b)


MatchFilter.__or__ = or_filter  # type: ignore


def and_filter(a, b):
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


@MATCH_FILTER_TYPE_REGISTRAR.register("duplicate_run")
class DuplicateMatchInRunFilter(MatchFilter):

    def __init__(self, order_dependent=False):
        self.order_dependent = order_dependent

    @property
    def parameters(self) -> dict[str, Any]:
        return {"order_dependent": self.order_dependent}

    @staticmethod
    def from_parameters(
        parameters: dict[str, Any], registrar: TypeRegistrar[MatchFilter]
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
            if prior_match.character_a.id == match[0]
            and prior_match.character_b.id == match[1]
        ):
            return True
        if not self.order_dependent and any(
            prior_match
            for prior_match in matches
            if prior_match.character_b.id == match[0]
            and prior_match.character_a.id == match[1]
        ):
            return True
        return False


@MATCH_FILTER_TYPE_REGISTRAR.register("duplicate_prior_run")
class DuplicateMatchInPriorRunFilter(MatchFilter):
    def __init__(
        self,
        results: list[MatchResult],
        order_dependent: bool = False,
        ignore_unfinished: bool = True,
        threshold: int = 1,
    ):
        # TODO: Take into account character attributes
        self.prior_matches = [
            (result.character_a.id, result.character_b.id)
            for result in results
            if (not ignore_unfinished)
            or (result.outcome in [Outcome.A_WINS, Outcome.B_WINS])
        ]
        self.order_dependent = order_dependent
        self.ignore_unfinished = ignore_unfinished
        self.threshold = threshold

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "order_dependent": self.order_dependent,
            "ignore_unfinished": self.ignore_unfinished,
            "threshold": self.threshold,
        }

    @staticmethod
    def from_parameters(
        parameters: dict[str, Any], registrar: TypeRegistrar[MatchFilter]
    ) -> MatchFilter:
        # TODO: Requires results, but none can be obtained from the object alone.
        raise NotImplementedError()
        # return DuplicateMatchInPriorRunFilter(
        #     None, parameters["order_dependent"], parameters["ignore_unfinished"]
        # )

    def ok(
        self,
        match: tuple[CharacterId, CharacterId],
        matches: list[PreparedMatch],
    ):
        num = 0
        for prior_match in self.prior_matches:
            if prior_match == match:
                num += 1
            elif (not self.order_dependent) and prior_match == (match[1], match[0]):
                num += 1
            else:
                continue
            if num >= self.threshold:
                return True
        return False


@MATCH_FILTER_TYPE_REGISTRAR.register("self")
class SelfMatchFilter(MatchFilter):
    @property
    def parameters(self):
        return {}

    @staticmethod
    def from_parameters(
        parameters: dict[str, Any], registrar: TypeRegistrar[MatchFilter]
    ) -> SelfMatchFilter:
        return SelfMatchFilter()

    def ok(
        self,
        potential_match: tuple[CharacterId, CharacterId],
        matches: list[PreparedMatch],
    ):
        return potential_match[0] == potential_match[1]


@MATCH_FILTER_TYPE_REGISTRAR.register("character_matches_threshold")
class CharacterMatchesThresholdFilter(MatchFilter):
    """Tests the number of matches in the current run that Character B is in."""

    def __init__(self, threshold: int):
        self.threshold = threshold

    @property
    def parameters(self):
        return {"threshold": self.threshold}

    @staticmethod
    def from_parameters(
        parameters: dict[str, Any], registrar: TypeRegistrar[MatchFilter]
    ) -> CharacterMatchesThresholdFilter:
        return CharacterMatchesThresholdFilter(parameters["threshold"])

    def ok(
        self,
        potential_match: tuple[CharacterId, CharacterId],
        matches: list[PreparedMatch],
    ):
        b_id = potential_match[1]
        b_matches = 1
        for match in matches:
            if b_id == match.character_a.id or b_id == match.character_b.id:
                b_matches += 1
                if b_matches > self.threshold:
                    return True
        return False
