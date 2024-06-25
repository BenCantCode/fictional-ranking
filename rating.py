from choix import ilsr_rankings
from match import MatchResult, Outcome
from character import CharacterId

DEFAULT_RATING = 0


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


def _results_to_tuples(
    results: list[MatchResult], id_to_int: dict[CharacterId, int]
) -> list[tuple[int, int]]:
    result_tuples = []
    for result in results:
        if result.outcome == Outcome.A_WINS:
            result_tuples.append(
                (id_to_int[result.character_a.id], id_to_int[result.character_b.id])
            )
        elif result.outcome == Outcome.B_WINS:
            result_tuples.append(
                (id_to_int[result.character_a.id], id_to_int[result.character_b.id])
            )
    return result_tuples


def rate_characters(results: list[MatchResult]) -> dict[CharacterId, float]:
    if len(results) == 0:
        return {}
    n, id_to_int, int_to_id = _map_characters(results)
    result_tuples = _results_to_tuples(results, id_to_int)
    raw_rankings = ilsr_rankings(n, result_tuples, alpha=0.0001)
    rankings = dict((int_to_id[i], raw_rankings[i]) for i in range(n))
    return rankings
