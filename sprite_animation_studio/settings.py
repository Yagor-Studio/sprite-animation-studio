# sprite_animation_studio/settings.py
import json
from .constants import CONFIG_DIR
from .logger import log

SETTINGS_FILE = CONFIG_DIR / "settings.json"

DEFAULTS = {
    "editor": {
        "autosave_enabled": False,
        "autosave_interval_sec": 120,
        "default_duration_ms": 120,
        "history_depth": 10,
    },
    "shortcuts": {
        "save":            "<Control-s>",
        "save_as":         "<Control-Shift-S>",
        "open":            "<Control-o>",
        "new":             "<Control-n>",
        "undo":            "<Control-z>",
        "redo":            "<Control-Shift-Z>",
        "play":            "<F5>",
        "pause":           "<F6>",
        "stop":            "<F7>",
        "next_frame":      "<Control-Right>",
        "prev_frame":      "<Control-Left>",
        "next_angle":      "<Control-Up>",
        "prev_angle":      "<Control-Down>",
        "export":          "<Control-e>",
    },
    "paths": {
        "last_export_dir": "",
    },
    "viewer": {
        "background_mode": "checker",
        "background_color": "#222222",
        "background_image": "",
        "background_fit": "cover",
    },
}


# Vincoli di validazione: chiave → (tipo, min, max)
# Se il valore letto non rispetta il tipo o l'intervallo,
# viene sostituito con il default.
EDITOR_CONSTRAINTS = {
    "autosave_enabled":    (bool, None, None),
    "autosave_interval_sec": (int, 15, 3600),
    "default_duration_ms": (int, 1, 10000),
    "history_depth":       (int, 1, 100),
}


class Settings:
    def __init__(self):
        self.data = json.loads(json.dumps(DEFAULTS))
        self.load()

    def load(self):
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, encoding="utf-8") as f:
                    saved = json.load(f)
                self._merge(saved)
                self._validate()
            except Exception as e:
                log.error(f"Settings load error: {e}", exc_info=True)

    def _merge(self, saved):
        for section, values in saved.items():
            if section in self.data and isinstance(values, dict):
                self.data[section].update(values)
            else:
                self.data[section] = values

    def _validate(self):
        """Corregge valori fuori range o di tipo sbagliato, riportandoli ai default."""
        editor = self.data.get("editor", {})
        defaults = DEFAULTS["editor"]

        for key, (typ, vmin, vmax) in EDITOR_CONSTRAINTS.items():
            value = editor.get(key)
            # Tipo sbagliato?
            if not isinstance(value, typ):
                # Prova a convertire, se possibile
                try:
                    if typ is int:
                        value = int(value)
                    elif typ is bool:
                        value = bool(value)
                except (TypeError, ValueError):
                    editor[key] = defaults[key]
                    continue
            # Fuori intervallo?
            if vmin is not None and value < vmin:
                editor[key] = vmin
            elif vmax is not None and value > vmax:
                editor[key] = vmax

        self.data["editor"] = editor

    def save(self):
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log.error(f"Settings save error: {e}", exc_info=True)

    def get(self, section, key=None, default=None):
        if key is None:
            return self.data.get(section, {})
        return self.data.get(section, {}).get(key, default)

    def set(self, section, key, value):
        self.data.setdefault(section, {})[key] = value
        self.save()