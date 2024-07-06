from __future__ import annotations
from abc import abstractmethod
import time
from character import CharacterId
from random import Random, getrandbits
from typing import Iterable, Any
from match import MatchResult, PreparedMatch
from match_filter import MatchFilter
from source_manager import SourceManager
from type_registrar import Type, TypeRegistrar
import json
from config import DEFAULT_RATING
from rating import ordinalize_ratings, invert_ratings, rate_characters
from character_filter import CharacterFilter
import bisect
from heapq import merge

MATCHMAKER_TYPE_REGISTRAR = TypeRegistrar["Matchmaker"]()


class Matchmaker(Type):
    TYPE_ID: str

    @abstractmethod
    def generate_matches(
        self,
        characters: list[CharacterId],
        match_filter: MatchFilter,
        matches: list[PreparedMatch],
        source_manager: SourceManager,
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
        registrar: TypeRegistrar[Matchmaker],
    ) -> Matchmaker:
        """Instantiate a filter from a JSON-deserialized object. Don't override this."""
        return registrar.get_type(object["type"]).from_parameters(object, registrar)

    @staticmethod
    @abstractmethod
    def from_parameters(
        parameters: dict[str, Any], registrar: TypeRegistrar[Matchmaker]
    ) -> Matchmaker:
        raise NotImplementedError()


@MATCHMAKER_TYPE_REGISTRAR.register("random")
class RandomMatchmaker(Matchmaker):
    def __init__(self, seed: int | None = None):
        if seed == None:
            seed = getrandbits(32)
        self.seed = seed

    def generate_matches(
        self,
        character_ids: list[CharacterId],
        filter: MatchFilter,
        matches: list[PreparedMatch],
        source_manager: SourceManager,
    ) -> Iterable[tuple[CharacterId, CharacterId]]:
        random = Random(self.seed)
        for character_id in character_ids:
            possible_opponent_ids = character_ids.copy()
            while True:
                opponent_id = possible_opponent_ids[
                    random.randint(0, len(possible_opponent_ids) - 1)
                ]
                match = (character_id, opponent_id)
                if filter.ok(match, matches, source_manager):
                    yield match
                    break
                possible_opponent_ids.remove(opponent_id)
                if len(possible_opponent_ids) == 0:
                    break

    @staticmethod
    def from_parameters(
        parameters: dict[str, Any], registrar: TypeRegistrar[Matchmaker]
    ) -> Matchmaker:
        return RandomMatchmaker(parameters["seed"])

    @property
    def parameters(self) -> dict[str, Any]:
        return {"seed": self.seed}


@MATCHMAKER_TYPE_REGISTRAR.register("powermatched")
class PowermatchingMatchmaker(Matchmaker):
    def __init__(
        self,
        ratings: dict[CharacterId, float],
        n: int | None = None,
        max_rating_difference: int | None = None,
    ):
        self.ratings = ratings
        self.n = n
        self.max_rating_difference = max_rating_difference

    @staticmethod
    def _find_closest_characters(
        rating: float,
        sorted_rated_characters: list[tuple[CharacterId, float]],
        max_rating_difference: float | None,
    ) -> Iterable[CharacterId]:
        if max_rating_difference is not None:
            min_index = bisect.bisect_left(
                sorted_rated_characters,
                rating - max_rating_difference,
                key=lambda c: c[1],
            )
            max_index = bisect.bisect_right(
                sorted_rated_characters,
                rating + max_rating_difference,
                key=lambda c: c[1],
            )
            sorted_rated_characters = sorted_rated_characters[min_index:max_index]
        middle_index = bisect.bisect(
            sorted_rated_characters, rating, key=lambda c: c[1]
        )
        left = sorted_rated_characters[:middle_index]
        right = sorted_rated_characters[middle_index:]
        return (
            c[0] for c in merge(reversed(left), right, key=lambda c: abs(c[1] - rating))
        )

    def generate_matches(
        self,
        character_ids: list[CharacterId],
        filter: MatchFilter,
        matches: list[PreparedMatch],
        source_manager: SourceManager,
    ) -> Iterable[tuple[CharacterId, CharacterId]]:
        sorted_rated_characters = [
            (character_id, self.ratings.get(character_id, DEFAULT_RATING))
            for character_id in character_ids
        ]
        sorted_rated_characters.sort(key=lambda c: c[1])
        if self.n is not None:
            print("num", len(character_ids))
            print("groups", self.n)
            grouped_characters = []
            min_rating = sorted_rated_characters[0][1]
            max_rating = sorted_rated_characters[-1][1]
            print("min:", min_rating, "max:", max_rating)
            rating_group_size = (max_rating - min_rating) / self.n
            min_group_index = 0
            grouped_characters = []
            for i in range(self.n):
                max_rating = min_rating + ((i + 1) * rating_group_size)
                if i != self.n - 1:
                    max_group_index = bisect.bisect_right(
                        sorted_rated_characters,
                        min_rating + ((i + 1) * rating_group_size),
                        key=lambda c: c[1],
                        lo=min_group_index,
                    )
                    unsorted_group = sorted_rated_characters[
                        min_group_index:max_group_index
                    ]
                else:
                    unsorted_group = sorted_rated_characters[min_group_index:]
                ideal_group_rating = (
                    min_rating + (i * rating_group_size) + (rating_group_size / 2)
                )
                sorted_group = self._find_closest_characters(
                    ideal_group_rating, unsorted_group, None
                )
                grouped_characters.append(sorted_group)
                min_group_index = max_group_index
        else:
            grouped_characters = [[c] for c in character_ids]
        # grouped_characters = [list(group) for group in list(grouped_characters)]
        # print([group[0:10] for group in grouped_characters])
        for group in grouped_characters:
            for character_id in group:
                found = False
                rating = self.ratings.get(character_id, DEFAULT_RATING)
                closest_opponents = self._find_closest_characters(
                    rating, sorted_rated_characters, self.max_rating_difference
                )
                for opponent_id in closest_opponents:
                    match = (character_id, opponent_id)
                    if filter.ok(match, matches, source_manager):
                        yield match
                        found = True
                        break
                if found:
                    break

    @staticmethod
    def from_parameters(
        parameters: dict[str, Any], registrar: TypeRegistrar[Matchmaker]
    ) -> Matchmaker:
        raise NotImplementedError()

    @property
    def parameters(self) -> dict[str, Any]:
        return {"n": self.n, "max_rating_difference": self.max_rating_difference}


@MATCHMAKER_TYPE_REGISTRAR.register("inverted_ordinalized_powermatched")
class InvertedOrdinalizedPowermatchingMatchmaker(PowermatchingMatchmaker):
    def __init__(
        self,
        ratings: dict[CharacterId, float],
        a_filter: CharacterFilter,
        b_filter: CharacterFilter,
        source_manager: SourceManager,
    ):
        self.a_filter = a_filter
        self.b_filter = b_filter
        a_ratings = ordinalize_ratings(
            {
                id: rating
                for id, rating in ratings.items()
                if a_filter.ok(id, source_manager)
            }
        )
        b_ratings = invert_ratings(
            ordinalize_ratings(
                {
                    id: rating
                    for id, rating in ratings.items()
                    if b_filter.ok(id, source_manager)
                }
            )
        )
        with open("a_ordinalized_ratings.txt", "w") as a_ratings_file:
            for id, rating in sorted(a_ratings.items(), key=lambda t: t[1]):
                a_ratings_file.write(f"{id}: {rating}\n")
        with open("b_ordinalized_inverted_ratings.txt", "w") as b_ratings_file:
            for id, rating in sorted(b_ratings.items(), key=lambda t: t[1]):
                b_ratings_file.write(f"{id}: {rating}\n")
        ratings = a_ratings | b_ratings
        with open("combined_ordinalized_inverted_ratings.txt", "w") as ratings_file:
            for id, rating in sorted(ratings.items(), key=lambda t: t[1]):
                ratings_file.write(f"{id}: {rating}\n")
        super().__init__(ratings)

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "a_filter": self.a_filter.to_object(),
            "b_filter": self.b_filter.to_object(),
        }
