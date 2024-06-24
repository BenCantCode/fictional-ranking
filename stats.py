from config import *
from evaluate import Evaluator
from source_manager import SourceManager
import logging
from character import CharacterId
from run import Run
from generator import Generator
from character_filter import SourceFilter, CharacterIdFilter
from match_filter import (
    InvertFilter,
    DuplicateMatchInRunFilter,
    AndFilter,
    SelfMatchFilter,
)
from matchmaking import PowermatchingMatchmaker, RandomMatchmaker
from db import RunsDatabase

logging.basicConfig(level=logging.INFO)
logging.getLogger("LiteLLM").setLevel(logging.WARNING)

source_manager = SourceManager()
source_manager.load_source("one_piece")
evaluator = Evaluator()
character_filter = CharacterIdFilter(
    [
        CharacterId("one_piece", "Roronoa Zoro"),
        CharacterId("one_piece", "Marshall D. Teach"),
    ]
)
match_filter = ~SelfMatchFilter() & ~DuplicateMatchInRunFilter()
matchmaker = RandomMatchmaker()
generator = Generator(
    character_filter, match_filter, matchmaker, source_manager.source_versions
)
db = RunsDatabase()
run = Run("first_run", generator, evaluator, db)
results = run.run(source_manager)
print(results)
