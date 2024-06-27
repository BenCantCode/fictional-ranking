import litellm
from os.path import join, dirname
from dotenv import load_dotenv
from character import CharacterId
from character_filter import CharacterFilterTypeRegistrar
from match_filter import MatchFilterTypeRegistrar
from matchmaking import MatchmakerTypeRegistrar

VERSION = "0.0.1"

load_dotenv()

# If you want to disable telemetry (see https://litellm.vercel.app/docs/observability/telemetry)
# litellm.telemetry = False

litellm.suppress_debug_info = True

DEBUG_DUMP = True
# DEBUG_DUMP_FILTER = [CharacterId("one_piece", "Charlotte Katakuri")]
DEBUG_DUMP_FILTER = None

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
TOKEN_LIMITED = True  # If true, rate limits based on tokens. If false, rate limits based on requests.
TOKENS_PER_INTERVAL = 200000
REQUESTS_PER_INTERVAL = 1000
INTERVAL_SECS = 60
MAX_OUTPUT_TOKENS_ESTIMATE = 4096  # Used when a model isn't known to LiteLLM.
EXECUTE_DELAY = 0.5  # To control "bursts"

NUM_RETRIES = 10


# Prompt (Jinja2 in toml)
PROMPT = "prompt_end.toml"

# Model (see LiteLLM docs)
# MODEL = "claude-3-haiku-20240307"
MODEL = "claude-3-5-sonnet-20240620"

# The arguments used in text generation
COMPLETION_ARGS = {
    # The temperature. A lower temperature value generally results in less creative responses.
    "temperature": 0,
    "timeout": 120,
}

CHARACTER_FILTER_TYPE_REGISTRAR = CharacterFilterTypeRegistrar()
MATCH_FILTER_TYPE_REGISTRAR = MatchFilterTypeRegistrar()
MATCHMAKER_TYPE_REGISTRAR = MatchmakerTypeRegistrar()
