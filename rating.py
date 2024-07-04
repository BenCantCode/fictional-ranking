from choix import ilsr_pairwise_dense
from character_filter import CharacterFilter
from config import MODEL_SCALING, DEFAULT_RATING, ALPHA, SCALE_FACTOR
from match import MatchResult, Outcome
from character import CharacterId
import numpy as np
import numpy.typing

from source_manager import SourceManager


def _map_characters(
    results: list[MatchResult],
) -> tuple[int, dict[CharacterId, int], dict[int, CharacterId]]:
    characters = set()
    for result in results:
        characters.add(result.character_a.id)
        characters.add(result.character_b.id)
    n = len(characters)
    int_to_id = dict(enumerate(characters))
    id_to_int = dict((v, k) for (k, v) in int_to_id.items())
    return (n, id_to_int, int_to_id)


def _results_to_matrix(
    n: int,
    results: list[MatchResult],
    id_to_int: dict[CharacterId, int],
    model_scaling: dict[str, float],
) -> numpy.typing.NDArray[np.float64]:
    matrix = np.zeros((n, n))
    for result in results:
        if result.outcome == Outcome.A_WINS:
            matrix[id_to_int[result.character_a.id]][
                id_to_int[result.character_b.id]
            ] += model_scaling.get(
                (
                    result.match_settings.model or "default"
                    if result.match_settings
                    else "default"
                ),
                model_scaling["default"],
            )
        elif result.outcome == Outcome.B_WINS:  # type: ignore
            matrix[id_to_int[result.character_b.id]][
                id_to_int[result.character_a.id]
            ] += model_scaling.get(
                (
                    result.match_settings.model or "default"
                    if result.match_settings
                    else "default"
                ),
                model_scaling["default"],
            )
    return matrix


def rate_characters(
    results: list[MatchResult],
    source_manager: SourceManager,
    model_scaling: dict[str, float] = MODEL_SCALING,
    filter: CharacterFilter | None = None,
) -> dict[CharacterId, float]:
    if len(results) == 0:
        return {}
    if filter:
        results = [
            result
            for result in results
            if filter.ok(result.character_a.id, source_manager)
            and filter.ok(result.character_b.id, source_manager)
        ]
    n, id_to_int, int_to_id = _map_characters(results)
    matrix = _results_to_matrix(n, results, id_to_int, model_scaling)
    raw_rankings = ilsr_pairwise_dense(matrix, alpha=ALPHA)
    rankings = dict(
        (int_to_id[i], raw_rankings[i] * SCALE_FACTOR + DEFAULT_RATING)
        for i in range(n)
    )
    return rankings


def invert_ratings(ratings: dict[CharacterId, float]):
    return dict(
        (id, DEFAULT_RATING - (rating - DEFAULT_RATING))
        for id, rating in ratings.items()
    )


def normalize_ratings(ratings: dict[CharacterId, float]) -> dict[CharacterId, float]:
    """Normalize ratings based on min/max rating and center around `DEFAULT_VALUE`."""
    normalized_ratings = {}
    max_rating = max(ratings.values())
    min_rating = min(ratings.values())
    rating_range = max_rating - min_rating
    for character_id, character_rating in ratings.items():
        normalized_ratings[character_id] = (
            ((character_rating - min_rating) / rating_range) * DEFAULT_RATING * 2
        )
    return normalized_ratings


def ordinalize_ratings(ratings: dict[CharacterId, float]) -> dict[CharacterId, float]:
    """Generate new ratings by sorting a previous set of ratings and evenly spacing values across an interval."""
    sorted_ratings = sorted(ratings.keys(), key=lambda id: ratings[id])
    ordinal_scale = DEFAULT_RATING * 2 / (len(ratings) - 1)
    return {id: i * ordinal_scale for i, id in enumerate(sorted_ratings)}
