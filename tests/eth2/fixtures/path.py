import os
from pathlib import Path


# ROOT_PROJECT_DIR = Path(__file__).cwd()
ROOT_PROJECT_DIR = Path(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
)
BASE_FIXTURE_PATH = ROOT_PROJECT_DIR / "eth2-fixtures" / "tests"
