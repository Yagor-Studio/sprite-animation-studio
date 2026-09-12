# sprite_studio/constants.py
from pathlib import Path

APP_NAME = "Sprite Animation Studio"
APP_VERSION = "0.7.0"
PROJECT_EXTENSION = ".sas"
IMG_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif")
DEFAULT_DURATION_MS = 112   # 4 tic a 35 Hz
TICK_MS = 28

CONFIG_DIR = Path.home() / ".sprite_studio"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
RECENT_FILE = CONFIG_DIR / "recent.json"