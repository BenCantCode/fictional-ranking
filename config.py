import litellm
from os.path import join, dirname
from dotenv import load_dotenv
from character_filter import CharacterFilterTypeRegistrar
from match_filter import MatchFilterTypeRegistrar
from matchmaking import MatchmakerTypeRegistrar

VERSION = "0.0.1"

load_dotenv()

# If you want to disable telemetry (see https://litellm.vercel.app/docs/observability/telemetry)
# litellm.telemetry = False

DEBUG_DUMP = False

# Folder locations
PROJECT_ROOT = dirname(__file__)
DEBUG_FOLDER = join(PROJECT_ROOT, "debug")
DOWNLOADS_FOLDER = join(PROJECT_ROOT, "downloads")
PROMPTS_FOLDER = join(PROJECT_ROOT, "prompts")
EVALS_FOLDER = join(PROJECT_ROOT, "evals")

# Information file
INFORMATION_FILE = join(PROJECT_ROOT, "information.toml")

# Database file (used for in-progress runs)
DB_PATH = join(PROJECT_ROOT, "runs.sqlite")

# Per-character limits
MAX_CHARACTERS = 100000
MAX_TOKENS = None
MAX_COST = None

# How often to print the running cost in a run
COST_UPDATE_INTERVAL = 0.10

# For rate limiting
REQUESTS_PER_INTERVAL = 10
INTERVAL_SECS = 60

# Prompt (Jinja2 in toml)
PROMPT = "prompt_end.toml"

# Model (see LiteLLM docs)
MODEL = "claude-3-haiku-20240307"

# The arguments used in text generation
COMPLETION_ARGS = {
    # The temperature. A lower temperature value generally results in less creative responses.
    "temperature": 0,
}

CHARACTER_FILTER_TYPE_REGISTRAR = CharacterFilterTypeRegistrar()
MATCH_FILTER_TYPE_REGISTRAR = MatchFilterTypeRegistrar()
MATCHMAKER_TYPE_REGISTRAR = MatchmakerTypeRegistrar()
