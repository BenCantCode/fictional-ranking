import sqlite3
from character_filter import CHARACTER_FILTER_TYPE_REGISTRAR, CharacterFilter
from config import *
from argparse import ArgumentParser
import json
from character import Character, CharacterId
from datetime import datetime
from enum import Enum
from match import MatchSettings, PreparedMatch, MatchResult, MatchCharacterMeta, Outcome
from match_filter import MATCH_FILTER_TYPE_REGISTRAR, MatchFilter
from matchmaking import MATCHMAKER_TYPE_REGISTRAR, Matchmaker
from run import Run, RunParameters

from typing import Iterable, Any, Literal, TypeAlias, TypedDict, TYPE_CHECKING

from source_manager import SourceManager
from type_registrar import TypeRegistrar

DB_FORMAT = 1

RunID: TypeAlias = int
MatchID: TypeAlias = int


class DbFormatMismatchException(Exception):
    pass


# Ensure changing the Match class doesn't affect the storage of the database.
_OUTCOME_TO_DB = {Outcome.A_WINS: 1, Outcome.B_WINS: 2, Outcome.ERROR: -1, None: None}
_DB_TO_OUTCOME = dict((v, k) for (k, v) in _OUTCOME_TO_DB.items())


def _raw_result_to_result(row: sqlite3.Row) -> MatchResult:
    return MatchResult(
        row["match_id"],
        row["run_id"],
        MatchCharacterMeta(
            CharacterId.from_str(row["a_id"]),
            row["a_revision"],
            row["a_attributes"],
        ),
        MatchCharacterMeta(
            CharacterId.from_str(row["b_id"]),
            row["b_revision"],
            row["b_attributes"],
        ),
        _DB_TO_OUTCOME[row["outcome"]],
        row["cost"],
        MatchSettings.from_object(json.loads(row["match_settings"])),
    )


class RunsDatabase:
    def __init__(self, db_path: str = DB_PATH):
        self.con = sqlite3.connect(db_path)
        self.con.row_factory = sqlite3.Row
        cur = self.con.cursor()
        self.initialized = False
        # Check version
        try:
            cur.execute("SELECT value FROM meta WHERE key = 'format'")
            format = int(cur.fetchone()[0])
            self.initialized = True
            if format != DB_FORMAT:
                raise DbFormatMismatchException(format)
        except sqlite3.OperationalError:
            pass

    def initialize_db(self):
        cur = self.con.cursor()
        cur.execute(
            "CREATE TABLE runs (run_id INTEGER PRIMARY KEY, run_name TEXT, run_params TEXT, dry_run INT, run_status INT, run_start TEXT)"
        )
        cur.execute(
            "CREATE TABLE matches (match_id INTEGER PRIMARY KEY, run_id INTEGER, match_settings TEXT, a_id TEXT, a_revision TEXT, a_attributes TEXT, b_id TEXT, b_revision TEXT, b_attributes TEXT, outcome INT, cost REAL, FOREIGN KEY(run_id) REFERENCES runs(run_id))"
        )
        cur.execute("CREATE TABLE meta (key TEXT, value TEXT)")
        cur.execute(
            "INSERT INTO meta VALUES ('format', ?)",
            (DB_FORMAT,),
        )
        self.con.commit()

    def start_run(self, run: Run) -> RunID:
        cur = self.con.cursor()
        cur.execute(
            "INSERT INTO runs VALUES (NULL, ?, ?, ?, 0, ?)",
            (
                run.name,
                json.dumps(run.to_object()),
                int(run.dry_run),
                str(datetime.now()),
            ),
        )
        self.con.commit()
        return cur.lastrowid  # type: ignore

    def _insert_match_raw(
        self,
        run_id: RunID | None,
        a_id: str,
        a_revision: str,
        b_id: str,
        b_revision: str,
        outcome: int | None,
        a_attributes: str = "{}",
        b_attributes: str = "{}",
        match_settings: str = "{}",
        cost: float | None = None,
    ) -> MatchID:
        cur = self.con.cursor()
        cur.execute(
            "INSERT INTO matches VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                match_settings,
                a_id,
                a_revision,
                a_attributes,
                b_id,
                b_revision,
                b_attributes,
                outcome,
                cost,
            ),
        )
        self.con.commit()
        return cur.lastrowid  # type: ignore

    def start_match(self, match: PreparedMatch) -> MatchID:
        # TODO: Include character attributes
        return self._insert_match_raw(
            match.run_id,
            str(match.character_a.id),
            match.character_a.revision,
            str(match.character_b.id),
            match.character_b.revision,
            _OUTCOME_TO_DB.get(match.outcome) if match.outcome else None,
        )

    def _update_match_raw(
        self,
        run_id: RunID,
        match_id: MatchID,
        a_id: str,
        a_revision: str,
        a_attributes: str,
        b_id: str,
        b_revision: str,
        b_attributes: str,
        outcome: int | None,
        cost: float | None,
        match_settings: str | None = None,
    ) -> MatchID:
        cur = self.con.cursor()
        if match_settings != None:
            cur.execute(
                "UPDATE matches SET run_id = ?, match_settings = ?, a_id = ?, a_revision = ?, a_attributes = ?, b_id = ?, b_revision = ?, b_attributes = ?, outcome = ?, cost = ? WHERE match_id = ?",
                (
                    run_id,
                    match_settings,
                    a_id,
                    a_revision,
                    a_attributes,
                    b_id,
                    b_revision,
                    b_attributes,
                    outcome,
                    cost,
                    match_id,
                ),
            )
        else:
            cur.execute(
                "UPDATE matches SET run_id = ?, a_id = ?, a_revision = ?, a_attributes = ?, b_id = ?, b_revision = ?, b_attributes = ?, outcome = ?, cost = ? WHERE match_id = ?",
                (
                    run_id,
                    a_id,
                    a_revision,
                    a_attributes,
                    b_id,
                    b_revision,
                    b_attributes,
                    outcome,
                    cost,
                    match_id,
                ),
            )
        self.con.commit()
        return cur.lastrowid  # type: ignore

    def update_match(self, match: MatchResult):
        # TODO: Include character attributes
        # TODO: More meaningful exception classes
        if match.run_id == None:
            raise Exception("Missing run id!")
        if match.match_id == None:
            raise Exception("Missing match id!")
        # TODO: Add character attributes
        return self._update_match_raw(
            match.run_id,
            match.match_id,
            str(match.character_a.id),
            match.character_a.revision,
            "{}",
            str(match.character_b.id),
            match.character_b.revision,
            "{}",
            _OUTCOME_TO_DB[match.outcome] if match.outcome else None,
            match.cost,
            match_settings=(
                json.dumps(match.match_settings.to_object())
                if match.match_settings
                else "{}"
            ),
        )

    def end_run(self, run: Run, successful: bool) -> RunID:
        cur = self.con.cursor()
        cur.execute(
            "UPDATE runs SET run_status = ? WHERE run_id = ?",
            (1 if successful else -1, run.run_id),
        )
        self.con.commit()
        return cur.lastrowid  # type: ignore

    class ResultsFilters(TypedDict):
        include_dry: bool | None
        run_id: RunID | None
        run_name: str | None

    def get_results(
        self,
        include_dry: bool = False,
        run_id: RunID | None = None,
        run_name: str | None = None,
        outcome: (
            Outcome | None | Literal["finished"] | Literal["unfinished"]
        ) = "finished",
    ) -> Iterable[MatchResult]:
        cur = self.con.cursor()
        if (
            "run_id" != None
            or "run_name" != None
            or "outcome" != None
            or "include_dry" == False
        ):
            query_base = "SELECT * FROM matches t1 WHERE "
        else:
            query_base = "SELECT * FROM matches t1 "
        query = []
        execute_args = []
        if run_id != None:
            query.append("run_id = ?")
            execute_args.append(run_id)
        if run_name != None:
            query.append("run_name = ?")
            execute_args.append(run_name)
        if include_dry == False:
            query.append(
                "((SELECT dry_run FROM runs t2 WHERE t1.run_id=t2.run_id) = 0)"
            )
        if outcome != None:
            if outcome == "finished":
                query.append("outcome IS NOT NULL")
            elif outcome == "unfinished":
                query.append("outcome IS NULL")
            else:
                query.append("outcome = ?")
                execute_args.append(_OUTCOME_TO_DB[outcome])

        cur.execute(query_base + " AND ".join(query), execute_args)
        for row in cur.fetchall():
            yield _raw_result_to_result(row)

    def _row_to_run(
        self,
        row: dict[str, Any],
        source_manager: SourceManager,
        character_filter_type_registrar: TypeRegistrar[CharacterFilter],
        matchmaker_type_registrar: TypeRegistrar[Matchmaker],
        match_filter_type_registrar: TypeRegistrar[MatchFilter],
        include_db=True,
    ) -> Run:
        params = RunParameters.from_object(
            json.loads(row["run_params"]),
            character_filter_type_registrar,
            matchmaker_type_registrar,
            match_filter_type_registrar,
        )
        results = list(self.get_results(run_id=row["run_id"], outcome="finished"))
        remaining_matches = [
            result.reprepare(
                self if include_db else None,
                source_manager,
            )
            for result in self.get_results(run_id=row["run_id"], outcome="unfinished")
        ]
        return Run(
            row["run_name"],
            params.generator,
            params.evaluator,
            self if include_db else None,
            row["dry_run"],
            row["run_id"],
            remaining_matches,
            results,
        )

    def get_run_by_id(
        self,
        run_id: RunID,
        source_manager: SourceManager,
        character_filter_type_registrar: TypeRegistrar[
            CharacterFilter
        ] = CHARACTER_FILTER_TYPE_REGISTRAR,
        matchmaker_type_registrar: TypeRegistrar[
            Matchmaker
        ] = MATCHMAKER_TYPE_REGISTRAR,
        match_filter_type_registrar: TypeRegistrar[
            MatchFilter
        ] = MATCH_FILTER_TYPE_REGISTRAR,
        include_db: bool = True,
    ):
        """Fully recreate a run from the database, including unfinished matches. May require re-parsing characters."""
        cur = self.con.cursor()
        cur.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
        row = cur.fetchone()
        return self._row_to_run(
            row,
            source_manager,
            character_filter_type_registrar,
            matchmaker_type_registrar,
            match_filter_type_registrar,
            include_db,
        )

    def get_run_by_name(
        self,
        run_name: str,
        source_manager: SourceManager,
        character_filter_type_registrar: TypeRegistrar[
            CharacterFilter
        ] = CHARACTER_FILTER_TYPE_REGISTRAR,
        matchmaker_type_registrar: TypeRegistrar[
            Matchmaker
        ] = MATCHMAKER_TYPE_REGISTRAR,
        match_filter_type_registrar: TypeRegistrar[
            MatchFilter
        ] = MATCH_FILTER_TYPE_REGISTRAR,
        include_db: bool = True,
    ):
        """Fully recreate a run from the database, including unfinished matches. May require re-parsing characters."""
        cur = self.con.cursor()
        cur.execute("SELECT * FROM runs WHERE run_name = ?", (run_name,))
        row = cur.fetchone()
        return self._row_to_run(
            row,
            source_manager,
            character_filter_type_registrar,
            matchmaker_type_registrar,
            match_filter_type_registrar,
            include_db,
        )


if __name__ == "__main__":
    # Parse arguments
    parser = ArgumentParser(
        prog="DB Manager",
        description="Perform various database actions via the command line",
    )
    parser.add_argument("-path")
    subparsers = parser.add_subparsers(dest="command")
    parser_init = subparsers.add_parser("init")
    parser_debug_start = subparsers.add_parser("debug_start")
    parser_debug_start.add_argument("run_name")
    parser_debug_end = subparsers.add_parser("debug_end")
    parser_debug_end.add_argument("run_name")
    parser_results = subparsers.add_parser("results")
    parser_results.add_argument("-run_name")
    parser_results.add_argument("-includedry", action="store_true")
    args = parser.parse_args()
    # Connect to DB
    db = RunsDatabase(args.path or DB_PATH)
    # Commands
    if args.command == "init":
        db.initialize_db()
    elif args.command == "debug_start":
        db.start_run(args.run_name)
    elif args.command == "debug_end":
        db.end_run(args.run_name, True)
    elif args.command == "results":
        # TODO: Add run name filtering
        print(list(db.get_results(include_dry=args.includedry)))
