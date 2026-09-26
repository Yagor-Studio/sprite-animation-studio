# sprite_animation_studio/blender_bridge.py
import json
from pathlib import Path
from typing import Callable, Optional

from .constants import MANIFEST_FILENAME, POLL_INTERVAL_MS
from .logger import log


class BlenderBridge:
    """Ponte Blender -> SAS.

    Sorveglia una cartella (tipicamente quella dove Blender scrive i render)
    e chiama `on_update(manifest_dict)` quando `manifest.json` cambia.

    Il polling è basato su `root.after`, quindi gira sul thread principale
    di Tk: la callback può aggiornare la UI direttamente, senza `queue`.
    """

    def __init__(self, watch_dir: Path, on_update_callback: Callable[[dict], None]):
        self.watch_dir = Path(watch_dir)
        self.on_update = on_update_callback
        self._last_mtime: float = 0.0
        self._after_id: Optional[str] = None
        self._root = None
        self._running = False

    # ------------------------------------------------------------------

    def start(self, root):
        """Avvia il polling. Idempotente."""
        self._root = root
        self._running = True
        self._last_mtime = 0.0     # forza rilettura al primo poll
        self._schedule()

    def stop(self):
        """Ferma il polling e cancella il callback pendente."""
        self._running = False
        if self._after_id is not None and self._root is not None:
            try:
                self._root.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    # ------------------------------------------------------------------

    def _schedule(self):
        if not self._running or self._root is None:
            return
        self._after_id = self._root.after(POLL_INTERVAL_MS, self._poll)

    def _poll(self):
        if not self._running:
            return
        try:
            self._poll_once()
        except Exception as e:
            # Non uccidere il loop per un errore transitorio (file lock, ecc.)
            log.error(f"Errore poll bridge: {e}", exc_info=True)
        self._schedule()

    def _poll_once(self):
        manifest_path = self.watch_dir / MANIFEST_FILENAME
        if not manifest_path.exists():
            return
        try:
            mtime = manifest_path.stat().st_mtime
        except OSError:
            return
        if mtime == self._last_mtime:
            return
        self._last_mtime = mtime
        self._process_manifest(manifest_path)

    def _process_manifest(self, manifest_path: Path):
        try:
            raw = manifest_path.read_text(encoding="utf-8")
        except OSError as e:
            log.error(f"Manifest illeggibile: {e}", exc_info=True)
            return
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            log.error(f"Manifest JSON invalido: {e}", exc_info=True)
            return
        try:
            self.on_update(data)
        except Exception as e:
            log.error(f"Errore nella callback bridge: {e}", exc_info=True)