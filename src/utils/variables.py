from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent
CONFIG_PATH = BASE_DIR.joinpath("config.yaml")
DB_PATH = BASE_DIR.joinpath("users.db")
DOWNLOAD_DIR = BASE_DIR.joinpath("downloads")
THROTTLE_RATE = 3.0  # seconds between actions
