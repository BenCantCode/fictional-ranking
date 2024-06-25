from __future__ import annotations


from evaluate import Evaluator
from typing import TYPE_CHECKING
from config import COST_UPDATE_INTERVAL, INTERVAL_SECS, REQUESTS_PER_INTERVAL
from math import ceil
from aiolimiter import AsyncLimiter
from asyncio import gather

from match import PreparedMatch

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
        dry_run: bool,
        id: RunID | None = None,
        requests_per_interval=REQUESTS_PER_INTERVAL,
        interval_secs=INTERVAL_SECS,
    ):
        self.name = name
        self.generator = generator
        self.evaluator = evaluator
        self.db = db
        self.run_id = id
        self.dry_run = dry_run

    def to_object(self):
        return {
            "generator": self.generator.to_object(),
            "evaluator": self.evaluator.to_object(),
        }

    async def run(
        self, source_manager: SourceManager, verbose: bool = False
    ) -> tuple[list[MatchResult], float]:
        print("Starting Run")
        if self.db:
            self.run_id = self.db.start_run(self)
        print("Generating Matches...")
        matches = list(self.generator.generate_matches(self, source_manager, self.db))
        results = []
        cost = 0
        next_cost_update = COST_UPDATE_INTERVAL
        rate_limit = AsyncLimiter(REQUESTS_PER_INTERVAL, INTERVAL_SECS)
        print("Running Matches...")
        coroutines = []
        for match in matches:

            async def evaluate(match: PreparedMatch):
                nonlocal cost, next_cost_update, results
                result = await match.evaluate(
                    self.evaluator, self.dry_run, verbose=verbose, rate_limit=rate_limit
                )
                if result.cost:
                    cost += result.cost
                    if cost > next_cost_update:
                        print("Running Cost", cost)
                        next_cost_update = (
                            ceil(cost / COST_UPDATE_INTERVAL) * COST_UPDATE_INTERVAL
                        )
                results.append(result)

            coroutines.append(evaluate(match))
        await gather(*coroutines)
        print("Done!")
        if self.db:
            self.db.end_run(self, True)
        return results, cost
