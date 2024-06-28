from __future__ import annotations

from aiolimiter import AsyncLimiter


from character import CharacterId
from evaluate import Evaluator
from generator import Generator
from typing import TYPE_CHECKING, Any
from config import (
    COST_UPDATE_INTERVAL,
    INTERVAL_SECS,
    REQUESTS_PER_INTERVAL,
    TOKENS_PER_INTERVAL,
)
from tqdm.asyncio import tqdm
from math import ceil
import logging

from character_filter import CharacterFilter
from match_filter import MatchFilter
from matchmaking import Matchmaker
from type_registrar import TypeRegistrar

logger = logging.getLogger(__name__)

from match import PreparedMatch

if TYPE_CHECKING:
    from db import RunsDatabase, RunID
    from match import MatchResult
    from source_manager import SourceManager


class RunParameters:
    def __init__(self, generator: Generator | None, evaluator: Evaluator | None):
        self.generator = generator
        self.evaluator = evaluator

    def to_object(self):
        return {
            "generator": self.generator.to_object() if self.generator else None,
            "evaluator": self.evaluator.to_object() if self.evaluator else None,
        }

    @staticmethod
    def from_object(
        object: dict[str, Any],
        character_filter_type_registrar: TypeRegistrar[CharacterFilter],
        matchmaker_type_registrar: TypeRegistrar[Matchmaker],
        match_filter_type_registrar: TypeRegistrar[MatchFilter],
    ):
        if object["generator"]:
            try:
                generator = Generator.from_object(
                    object["generator"],
                    character_filter_type_registrar,
                    matchmaker_type_registrar,
                    match_filter_type_registrar,
                )
            except NotImplementedError as e:
                logger.warn("Cannot reserialize generator: %s", str(e))
                generator = None
        else:
            generator = None
        if object["evaluator"]:
            try:
                evaluator = Evaluator.from_object(object["evaluator"])
            except NotImplementedError as e:
                logger.warn("Cannot reserialize evaluator: %s", str(e))
                evaluator = None
        else:
            generator = None
        return RunParameters(generator, evaluator)


class Run:
    def __init__(
        self,
        name: str,
        generator: Generator | None,
        evaluator: Evaluator | None,
        db: RunsDatabase | None,
        dry_run: bool,
        id: RunID | None = None,
        remaining_matches: list[PreparedMatch] | None = None,
        results: list | None = None,
    ):
        self.name = name
        self.settings = RunParameters(generator, evaluator)
        self.db = db
        self.run_id = id
        self.dry_run = dry_run
        self.remaining_matches = remaining_matches
        self.results = results or []

    def to_object(self):
        return self.settings.to_object()

    async def start(
        self,
        source_manager: SourceManager,
        rate_limit: AsyncLimiter,
        verbose: bool = False,
        cost_update_interval=COST_UPDATE_INTERVAL,
    ) -> tuple[list[MatchResult], float]:
        print("Starting Run")
        if self.db and not self.run_id:
            self.run_id = self.db.start_run(self)
        if self.remaining_matches == None:
            print("Generating Matches...")
            if self.settings.generator == None:
                raise ValueError("Cannot generate matches without a generator!")
            self.remaining_matches = list(
                self.settings.generator.generate_matches(self, source_manager, self.db)
            )
        if self.results == None:
            self.results = []
        cost = 0
        next_cost_update = cost_update_interval
        print("Running Matches...")
        coroutines = []
        if self.remaining_matches != None and self.settings.evaluator == None:
            raise ValueError("Cannot evaluator matches without an evaluator!")
        for match in self.remaining_matches:

            async def evaluate(match: PreparedMatch):
                nonlocal cost, next_cost_update
                result = await match.evaluate(
                    self.settings.evaluator,  # type: ignore
                    self.dry_run,
                    rate_limit,
                    verbose=verbose,
                    debug_dump_prefix=str(self.name),
                )
                if result.cost:
                    cost += result.cost
                    if cost > next_cost_update:
                        print("Running Cost", cost)
                        next_cost_update = (
                            ceil(cost / cost_update_interval) * cost_update_interval
                        )
                self.results.append(result)

            coroutines.append(evaluate(match))
        await tqdm.gather(*coroutines)
        print("Done!")
        if self.db:
            self.db.end_run(self, True)
        return self.results, cost
