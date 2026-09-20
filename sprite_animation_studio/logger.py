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

LOG_FILE = CONFIG_DIR / "sprite_animation_studio.log"
LOG_MAX_BYTES = 1_000_000       # 1 MB per file
LOG_BACKUP_COUNT = 3            # 3 file storici + corrente

_logger = None


def _build_logger() -> logging.Logger:
    logger = logging.getLogger("sprite_animation_studio")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    # File handler con rotazione
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
        # Se non riusciamo a scrivere il log, non blocchiamo l'app.
        # Un messaggio su stderr avvisa chi ha lanciato da console.
        print(f"[logger] impossibile creare {LOG_FILE}: {e}", file=sys.stderr)

    # Console handler solo se stiamo girando da sorgente (non dall'.exe)
    if not getattr(sys, 'frozen', False):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_formatter = logging.Formatter(
            "%(levelname)s: %(message)s"
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    return logger


def get_logger() -> logging.Logger:
    global _logger
    if _logger is None:
        _logger = _build_logger()
    return _logger


# Alias comodo
log = get_logger()


def get_log_path() -> Path:
    """Percorso del file di log corrente. Utile per il menu 'Apri cartella log'."""
    return LOG_FILE


def open_log_folder():
    """Apre la cartella che contiene il log nel file manager di sistema."""
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