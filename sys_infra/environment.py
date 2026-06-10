import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

REPO_ROOT = Path(os.getenv("REPO_ROOT", "."))
LIB_DIR = REPO_ROOT / "lib"

SCRIPTS_DIR = REPO_ROOT / "scripts"
EXAMPLES_BILGEPUMP_DIR = REPO_ROOT / "examples" / "bilgepump"
