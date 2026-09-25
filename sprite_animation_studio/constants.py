# sprite_animation_studio/constants.py
from pathlib import Path

APP_NAME = "Sprite Animation Studio"
APP_VERSION = "0.8.4"
SCHEMA_DEFAULT = "8 CAM DOOM"
PROJECT_EXTENSION = ".sas"
IMG_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif")
DEFAULT_DURATION_MS = 112   # 4 tic a 35 Hz
TICK_MS = 28

CONFIG_DIR = Path.home() / ".sprite_animation_studio"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
RECENT_FILE = CONFIG_DIR / "recent.json"

MANIFEST_FILENAME = "manifest.json"
POLL_INTERVAL_MS = 500   # 1 secondo