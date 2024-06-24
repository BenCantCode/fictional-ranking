from __future__ import annotations


from evaluate import Evaluator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from db import RunsDatabase, RunID
    from generator import Generator
    from match import MatchResult
    from source_manager import SourceManager


class Run:
    def __init__(
        self,
        name: str,
        generator: Generator,
        evaluator: Evaluator,
        db: RunsDatabase | None,
        id: RunID | None = None,
    ):
        self.name = name
        self.generator = generator
        self.evaluator = evaluator
        self.db = db
        self.run_id = id

    def to_object(self):
        return {
            "generator": self.generator.to_object(),
            "evaluator": self.evaluator.to_object(),
        }

    def run(self, source_manager: SourceManager) -> list[MatchResult]:
        if self.db:
            self.run_id = self.db.start_run(self)
        matches = list(self.generator.generate_matches(self, source_manager, self.db))
        results = []
        for match in matches:
            results.append(match.evaluate(self.evaluator))
        return results
