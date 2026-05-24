import os
from pathlib import Path

BASE_DIR = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
DB_PATH = os.path.join(str(BASE_DIR), "users.db")
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", os.path.join(str(BASE_DIR), "downloads")))
THROTTLE_RATE = 3.0  # seconds between actions
