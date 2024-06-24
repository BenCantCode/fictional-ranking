from __future__ import annotations
from character import Character, CharacterId

from enum import Enum
from exceptions import InvalidResult
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from db import RunsDatabase, RunID, MatchID
    from source_manager import SourceManager
    from evaluate import Evaluator


class Outcome(Enum):
    A_WINS = 1
    B_WINS = 2
    ERROR = -1


class MatchCharacterMeta:
    def __init__(self, id: CharacterId, revision: str, attributes: dict[str, Any]):
        self.id = id
        self.revision = revision
        self.attributes = attributes

    @staticmethod
    def from_character(character: Character, attributes={}):
        return MatchCharacterMeta(character.id, character.revision, attributes)

    def get(self, source_manager: SourceManager):
        return source_manager.get_character(self.id)


class PreparedMatch:
    """A match that is about to occur."""

    def __init__(
        self,
        run_id: RunID | None,
        character_a: Character,
        character_b: Character,
        db: RunsDatabase | None,
        done: bool = False,
        match_id: MatchID | None = None,
        outcome: Outcome | None = None,
    ):
        """
        Initialize a PreparedMatch object.
        If `db` is provided, the math will be added to the database (if `row_id` is not provided)
        and the database entry will be updated when the math is run.
        """
        self.match_id = match_id
        self.run_id = run_id
        self.character_a = character_a
        self.character_b = character_b
        self.done = done
        self.outcome = outcome
        self.db = db
        if db and match_id == None:
            self.match_id = db.start_match(self)

    def evaluate(self, evaluator: Evaluator, **evaluation_args) -> MatchResult:
        """
        Run a prepared match using the provided `evaluator`.
        If the PreparedMatch instance contains a `RunsDatabase` reference (as provided in the initializer),
        the database will be updated with the result of the match.
        """
        try:
            winner, loser = evaluator.evaluate(
                self.character_a,
                self.character_b,
                **evaluation_args,
            )
            outcome = None
            if winner.id == self.character_a.id:
                outcome = Outcome.A_WINS
            elif winner.id == self.character_b.id:
                outcome = Outcome.B_WINS
            else:
                raise InvalidResult(f"By God, it's {winner.id} with a steel chair!!")
        except:
            outcome = Outcome.ERROR
            pass
        self.result = MatchResult(
            self.match_id,
            self.run_id,
            # TODO: Add character attributes
            MatchCharacterMeta.from_character(self.character_a, {}),
            MatchCharacterMeta.from_character(self.character_b, {}),
            outcome,
        )
        if self.db:
            self.db.update_match(self.result)
        return self.result


class MatchResult:
    def __init__(
        self,
        match_id: MatchID | None,
        run_id: RunID | None,
        character_a: MatchCharacterMeta,
        character_b: MatchCharacterMeta,
        outcome: Outcome,
    ):
        self.match_id = match_id
        self.run_id = run_id
        self.character_a = character_a
        self.character_b = character_b
        self.outcome = outcome
