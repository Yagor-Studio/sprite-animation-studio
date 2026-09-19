# sprite_studio/project_manager.py
import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Optional

from .constants import RECENT_FILE, PROJECT_EXTENSION
from .models import ProjectData

BACKUP_SUFFIX = ".bak"


class ProjectManager:
    def __init__(self):
        self.current_project: Optional[ProjectData] = None
        self._load_recent()

    # ------------------------------------------------------------------
    # CREAZIONE
    # ------------------------------------------------------------------

    def create_project(self, root_path: Path, name: str, mode: str = "DooMod",
                       force: bool = False) -> ProjectData:
        """Crea un nuovo progetto.

        Se esiste già un .sas con lo stesso nome e force=False,
        solleva ProjectAlreadyExists.
        Se force=True, lo sovrascrive — ma il .sas precedente viene
        conservato come .bak da _save_project() prima della sostituzione.
        """
        project_path = root_path / name
        sas_path = project_path / f"{name}{PROJECT_EXTENSION}"

        if sas_path.exists() and not force:
            raise ProjectAlreadyExists(sas_path)

        project_path.mkdir(parents=True, exist_ok=True)
        project = ProjectData(
            name=name,
            root_path=project_path,
            created=datetime.now().isoformat(),
            mode=mode,
            profiles=[],
        )
        self.current_project = project
        self._save_project()
        self._add_recent(sas_path)
        return project

    # ------------------------------------------------------------------
    # SALVATAGGIO (atomico + backup)
    # ------------------------------------------------------------------

    def _save_project(self) -> bool:
        if not self.current_project:
            return False

        sas_path = self.current_project.root_path / \
            f"{self.current_project.name}{PROJECT_EXTENSION}"
        backup_path = sas_path.with_suffix(sas_path.suffix + BACKUP_SUFFIX)
        tmp_path = sas_path.with_suffix(sas_path.suffix + ".tmp")

        try:
            # 1) Scrivi su file temporaneo nella stessa cartella
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self.current_project.to_dict(), f, indent=2)
                f.flush()

            # 2) Se esiste una versione valida, conservala come backup
            if sas_path.exists():
                try:
                    shutil.copy2(sas_path, backup_path)
                except OSError:
                    # Se il backup fallisce non blocchiamo il salvataggio
                    pass

            # 3) Sostituisci (atomico su Windows e Unix)
            tmp_path.replace(sas_path)
            return True

        except Exception as e:
            print(f"Errore salvataggio: {e}")
            # Pulizia del temporaneo, se è rimasto
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except OSError:
                pass
            return False

    # ------------------------------------------------------------------
    # CARICAMENTO
    # ------------------------------------------------------------------

    def load_project(self, sas_path: Path) -> Optional[ProjectData]:
        if not sas_path.exists():
            return None

        # Prova il file principale
        project = self._try_load(sas_path)
        if project is not None:
            self.current_project = project
            self._add_recent(sas_path)
            return project

        # Fallback: prova il backup
        backup_path = sas_path.with_suffix(sas_path.suffix + BACKUP_SUFFIX)
        if backup_path.exists():
            project = self._try_load(backup_path)
            if project is not None:
                # Ripristina il backup come file principale
                try:
                    shutil.copy2(backup_path, sas_path)
                except OSError:
                    pass
                self.current_project = project
                self._add_recent(sas_path)
                return project

        return None

    def _try_load(self, path: Path) -> Optional[ProjectData]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return ProjectData.from_dict(data, path.parent)
        except Exception as e:
            print(f"Caricamento fallito da {path.name}: {e}")
            return None

    # ------------------------------------------------------------------
    # RECENTI
    # ------------------------------------------------------------------

    def _load_recent(self):
        self.recent_projects: List[Path] = []
        if RECENT_FILE.exists():
            try:
                with open(RECENT_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.recent_projects = [
                        Path(p) for p in data.get("recent", [])
                        if Path(p).exists()
                    ]
            except Exception:
                pass

    def add_recent(self, path: Path):
        """Versione pubblica per _save_as che non passa per il load."""
        self._add_recent(path)

    def _add_recent(self, path: Path):
        if path in self.recent_projects:
            self.recent_projects.remove(path)
        self.recent_projects.insert(0, path)
        if len(self.recent_projects) > 10:
            self.recent_projects = self.recent_projects[:10]
        self._save_recent()

    def _save_recent(self):
        try:
            with open(RECENT_FILE, "w", encoding="utf-8") as f:
                json.dump({"recent": [str(p) for p in self.recent_projects]},
                          f, indent=2)
        except Exception:
            pass

    def get_recent(self) -> List[Path]:
        return self.recent_projects


# ------------------------------------------------------------------
# ECCEZIONI
# ------------------------------------------------------------------

class ProjectAlreadyExists(Exception):
    """Il .sas esiste già nella cartella scelta."""
    def __init__(self, path: Path):
        self.path = path
        super().__init__(f"Progetto già esistente: {path}")