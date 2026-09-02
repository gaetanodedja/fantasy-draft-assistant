from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = APP_ROOT.parent
DATA_DIR = PROJECT_ROOT / "data"
DATASET_PATH = DATA_DIR / "fantasy_dataset.csv"
DEFAULT_LEAGUE_BUDGET = 1000.0
TEAM_COUNT = 20

POSITION_ORDER = ["FW", "MID", "DEF", "GK"]
