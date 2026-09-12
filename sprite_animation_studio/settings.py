# sprite_studio/settings.py
import json
from pathlib import Path
from .constants import CONFIG_DIR

SETTINGS_FILE = CONFIG_DIR / "settings.json"

DEFAULTS = {
    "editor": {
        "autosave_enabled": False,
        "autosave_interval_sec": 120,
        "default_duration_ms": 120,
    },
    "shortcuts": {
        "save":            "<Control-s>",
        "save_as":         "<Control-Shift-S>",
        "open":            "<Control-o>",
        "new":             "<Control-n>",
        "play":            "<F5>",
        "pause":           "<F6>",
        "stop":            "<F7>",
        "next_frame":      "<Control-Right>",
        "prev_frame":      "<Control-Left>",
        "next_angle":      "<Control-Up>",
        "prev_angle":      "<Control-Down>",
    },
    "paths": {
        "last_export_dir": "",
    },
}


class Settings:
    def __init__(self):
        self.data = json.loads(json.dumps(DEFAULTS))
        self.load()

    def load(self):
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE) as f:
                    saved = json.load(f)
                self._merge(saved)
            except Exception as e:
                print(f"Settings load error: {e}")

    def _merge(self, saved):
        for section, values in saved.items():
            if section in self.data and isinstance(values, dict):
                self.data[section].update(values)
            else:
                self.data[section] = values

    def save(self):
        try:
            with open(SETTINGS_FILE, 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            print(f"Settings save error: {e}")

    def get(self, section, key=None, default=None):
        if key is None:
            return self.data.get(section, {})
        return self.data.get(section, {}).get(key, default)

    def set(self, section, key, value):
        self.data.setdefault(section, {})[key] = value
        self.save()