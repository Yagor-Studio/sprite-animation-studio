# sprite_animation_studio/logger.py
"""Sistema di logging centralizzato.

Scrive su un file di log nella cartella di configurazione, con rotazione
automatica (3 file da 1 MB ciascuno). Sostituisce i print sparsi nel codice.

Uso:
    from .logger import log
    log.info("messaggio")
    log.warning("messaggio")
    log.error("messaggio", exc_info=True)
"""

import logging
import logging.handlers
import sys
from pathlib import Path

from .constants import CONFIG_DIR

LOG_FILE = CONFIG_DIR / "sprite_studio.log"
LOG_MAX_BYTES = 1_000_000
LOG_BACKUP_COUNT = 3

_logger = None


def _build_logger() -> logging.Logger:
    logger = logging.getLogger("sprite_studio")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    try:
        file_handler = logging.handlers.RotatingFileHandler(
            LOG_FILE, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            "%(asctime)s  [%(levelname)-7s]  %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        sys.stderr.write(f"[logger] impossibile creare {LOG_FILE}: {e}\n")

    if not getattr(sys, 'frozen', False):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_formatter = logging.Formatter("%(levelname)s: %(message)s")
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    return logger


def get_logger() -> logging.Logger:
    global _logger
    if _logger is None:
        _logger = _build_logger()
    return _logger


log = get_logger()


def get_log_path() -> Path:
    return LOG_FILE


def open_log_folder():
    import subprocess
    import os
    folder = LOG_FILE.parent
    try:
        if sys.platform == "win32":
            os.startfile(folder)
        elif sys.platform == "darwin":
            subprocess.run(["open", str(folder)])
        else:
            subprocess.run(["xdg-open", str(folder)])
    except Exception as e:
        log.error(f"Impossibile aprire cartella log: {e}", exc_info=True)