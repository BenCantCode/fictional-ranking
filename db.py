import sqlite3
from config import *
from argparse import ArgumentParser
import json
from character import Character
from datetime import datetime
from enum import Enum
from match import PreparedMatch, MatchResult, MatchCharacterMeta, Outcome
from run import Run

from typing import Iterable, Any, TypeAlias

DB_FORMAT = 1

RunID: TypeAlias = int
MatchID: TypeAlias = int


class DbFormatMismatchException(Exception):
    pass


# Ensure changing the Match class doesn't affect the storage of the database.
_OUTCOME_TO_DB = {Outcome.A_WINS: 1, Outcome.B_WINS: 2, Outcome.ERROR: -1}
_DB_TO_OUTCOME = dict((v, k) for (k, v) in _OUTCOME_TO_DB.items())


def _raw_result_to_result(row: sqlite3.Row) -> MatchResult:
    return MatchResult(
        row["match_id"],
        row["run_name"],
        MatchCharacterMeta(
            row["character_a_id"],
            row["character_a_revision"],
            row["character_a_attributes"],
        ),
        MatchCharacterMeta(
            row["character_b_id"],
            row["character_b_revision"],
            row["character_b_attributes"],
        ),
        _DB_TO_OUTCOME[row["outcome"]],
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
            "CREATE TABLE runs (run_id INTEGER PRIMARY KEY, run_name TEXT, run_params TEXT, run_status INT, run_start TEXT)"
        )
        cur.execute(
            "CREATE TABLE matches (match_id INTEGER PRIMARY KEY, FOREIGN KEY(run_id) REFERENCES runs(run_id), match_settings TEXT, a_id TEXT, a_revision TEXT, a_attrs TEXT, b_id TEXT, b_revision TEXT, b_attrs TEXT, outcome INT)"
        )
        cur.execute("CREATE TABLE meta (key TEXT, value TEXT)")
        cur.execute(
            "INSERT INTO meta VALUES ('format', ?)",
            (DB_FORMAT,),
        )
        self.con.commit()

    def start_run(self, run: Run):
        cur = self.con.cursor()
        cur.execute(
            "INSERT INTO runs VALUES (NULL, ?, ?, 0, ?)",
            (run.name, json.dumps(run.to_object()), str(datetime.now())),
        )
        self.con.commit()

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
    ):
        cur = self.con.cursor()
        cur.execute(
            "INSERT INTO matches VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
            ),
        )
        self.con.commit()

    def start_match(self, match: PreparedMatch):
        # TODO: Include character attributes
        self._insert_match_raw(
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
        b_id: str,
        b_revision: str,
        outcome: int | None,
        a_attributes: str = "{}",
        b_attributes: str = "{}",
        match_settings: str = "{}",
    ):
        cur = self.con.cursor()
        cur.execute(
            "UPDATE matches SET run_id = ?, match_settings = ?, a_id = ?, a_revision = ?, a_attributes = ?, b_id = ?, b_revision = ?, b_attributes = ?, outcome = ? WHERE id = ?",
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
                match_id,
            ),
        )
        self.con.commit()

    def update_match(self, match: MatchResult):
        # TODO: Include character attributes
        # TODO: More meaningful exception classes
        if match.run_id == None:
            raise Exception("Missing run id!")
        if match.match_id == None:
            raise Exception("Missing match id!")

        self._update_match_raw(
            match.match_id,
            match.match_id,
            str(match.character_a.id),
            match.character_a.revision,
            str(match.character_b.id),
            match.character_b.revision,
            _OUTCOME_TO_DB.get(match.outcome) if match.outcome else None,
        )

    def end_run(self, run_name: str, successful: bool):
        cur = self.con.cursor()
        cur.execute(
            "UPDATE runs SET status = ? WHERE name = ?",
            (1 if successful else -1, run_name),
        )
        self.con.commit()

    def get_results(self) -> Iterable[MatchResult]:
        cur = self.con.cursor()
        cur.execute("SELECT * FROM matches")
        for row in cur.fetchall():
            yield _raw_result_to_result(row)


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
        results = db.get_results()
        if args.run_name:
            # test
            pass
        else:
            print(results)
