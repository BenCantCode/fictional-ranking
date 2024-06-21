import litellm
from os.path import join, dirname
from dotenv import load_dotenv

load_dotenv()

# If you want to disable telemetry (see https://litellm.vercel.app/docs/observability/telemetry)
# litellm.telemetry = False

DEBUG_DUMP = True

# Folder locations
PROJECT_ROOT = dirname(__file__)
DEBUG_FOLDER = join(PROJECT_ROOT, "debug")
DOWNLOADS_FOLDER = join(PROJECT_ROOT, "downloads")
PROMPTS_FOLDER = join(PROJECT_ROOT, "prompts")
EVALS_FOLDER = join(PROJECT_ROOT, "evals")

# Information file
INFORMATION_FILE = join(PROJECT_ROOT, "information.toml")

# Per-character limits
MAX_CHARACTERS = 100000
MAX_TOKENS = None
MAX_COST = None

# Prompt (Jinja2 in toml)
PROMPT = "prompt_end.toml"

# Model (see LiteLLM docs)
MODEL = "claude-3-haiku-20240307"

# The arguments used in text generation
COMPLETION_ARGS = {
    # The temperature. A lower temperature value generally results in less creative responses.
    "temperature": 0,
}
