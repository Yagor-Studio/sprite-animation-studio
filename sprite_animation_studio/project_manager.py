# sprite_animation_studio/project_manager.py
import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Optional

from .constants import RECENT_FILE, PROJECT_EXTENSION
from .models import ProjectData
from .logger import log

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
        Se force=True, lo sovrascrive — ma il .sas precedente viene prima
        copiato in <nome>.sas.overwritten_<timestamp>.bak, che nessun
        salvataggio successivo tocca (il .bak di _save_project() invece
        viene riscritto a ogni salvataggio). Allo stesso modo, se esiste,
        il .bak viene copiato in <nome>.sas.bak.overwritten_<timestamp>.bak.
        """
        project_path = root_path / name
        sas_path = project_path / f"{name}{PROJECT_EXTENSION}"

        if sas_path.exists() and not force:
            raise ProjectAlreadyExists(sas_path)

        if force and sas_path.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            permanent_backup = sas_path.with_name(
                f"{sas_path.stem}.sas.overwritten_{timestamp}.bak")
            try:
                shutil.copy2(sas_path, permanent_backup)
                log.info(f"Progetto sovrascritto: backup permanente in {permanent_backup}")
            except OSError as e:
                # Non blocchiamo la creazione: resta il .bak di _save_project()
                log.warning(f"Backup permanente di {sas_path.name} non riuscito: {e}")

            # Anche il .bak: se il .sas è corrotto è l'unica copia buona, e
            # _save_project() sta per sovrascriverlo con il file corrotto
            backup_path = sas_path.with_suffix(sas_path.suffix + BACKUP_SUFFIX)
            if backup_path.exists():
                permanent_bak = backup_path.with_name(
                    f"{backup_path.name}.overwritten_{timestamp}.bak")
                try:
                    shutil.copy2(backup_path, permanent_bak)
                    log.info(f"Progetto sovrascritto: .bak conservato in {permanent_bak}")
                except OSError as e:
                    log.warning(f"Copia permanente di {backup_path.name} non riuscita: {e}")

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
            log.error(f"Errore salvataggio: {e}", exc_info=True)
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

    def load_project(self, sas_path: Path, on_corrupt=None) -> Optional[ProjectData]:
        """Carica un progetto .sas.

        Se il file principale è illeggibile viene rinominato in .corrupt
        (mai sovrascritto). Se esiste un .bak leggibile:
          - on_corrupt None: ripristino silenzioso del backup (atomico);
          - altrimenti on_corrupt(corrupt_path, backup_path, backup_date_str)
            decide: "load_backup" ripristina e carica, qualsiasi altro
            valore annulla e ritorna None.
        """
        if not sas_path.exists():
            return None

        # Prova il file principale
        project = self._try_load(sas_path)
        if project is not None:
            self.current_project = project
            self._add_recent(sas_path)
            return project

        # File principale illeggibile: calcola dove finirebbe una volta
        # rinominato, ma non toccarlo finché l'utente non ha deciso.
        corrupt_path = self._compute_corrupt_path(sas_path)

        # Fallback: prova il backup
        backup_path = sas_path.with_suffix(sas_path.suffix + BACKUP_SUFFIX)
        if not backup_path.exists():
            log.warning(f"Nessun backup disponibile per {sas_path.name}")
            return None

        project = self._try_load(backup_path)
        if project is None:
            log.warning(f"Backup illeggibile: {backup_path.name}")
            return None

        try:
            backup_date_str = datetime.fromtimestamp(
                backup_path.stat().st_mtime).strftime("%d/%m/%Y %H:%M:%S")
        except OSError:
            backup_date_str = "data sconosciuta"

        # Se la UI ha fornito un callback, è l'utente a decidere
        if on_corrupt is not None:
            # Un'eccezione nel callback equivale ad "annulla"
            try:
                decision = on_corrupt(corrupt_path, backup_path, backup_date_str)
            except Exception as e:
                log.error(f"on_corrupt ha sollevato: {e}", exc_info=True)
                decision = None
            if decision != "load_backup":
                return None

        # Solo ora, deciso il ripristino, metti da parte il file corrotto
        try:
            corrupt_path = self._rename_corrupt(sas_path)
        except OSError as e:
            # Senza rinomina un ripristino distruggerebbe il file corrotto
            log.error(f"Impossibile rinominare il file corrotto {sas_path.name}: {e}",
                      exc_info=True)
            return None
        log.warning(f"File progetto corrotto rinominato in {corrupt_path.name}")

        # Ripristina il backup come file principale (tmp + replace)
        try:
            self._atomic_restore(backup_path, sas_path)
        except OSError as e:
            log.error(f"Ripristino backup su {sas_path.name} fallito: {e}",
                      exc_info=True)
        log.warning(f"Progetto caricato dal backup {backup_path.name} "
                    f"del {backup_date_str}")
        self.current_project = project
        self._add_recent(sas_path)
        return project

    def _compute_corrupt_path(self, sas_path: Path) -> Path:
        """Calcola dove finirebbe il file corrotto senza rinominarlo."""
        corrupt_path = sas_path.with_name(sas_path.name + ".corrupt")
        if corrupt_path.exists():
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            corrupt_path = sas_path.with_name(f"{sas_path.name}.corrupt.{stamp}")
        return corrupt_path

    def _rename_corrupt(self, sas_path: Path) -> Path:
        """Rinomina il file corrotto in <nome>.sas.corrupt, oppure in
        <nome>.sas.corrupt.YYYYMMDD_HHMMSS se il primo esiste già.
        Ritorna il nuovo percorso. Solleva OSError se la rinomina fallisce."""
        corrupt_path = sas_path.with_name(sas_path.name + ".corrupt")
        if corrupt_path.exists():
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            corrupt_path = sas_path.with_name(f"{sas_path.name}.corrupt.{stamp}")
        sas_path.rename(corrupt_path)
        return corrupt_path

    def _atomic_restore(self, src: Path, dst: Path) -> None:
        """Copia src su dst in modo atomico: tmp nella stessa cartella + replace.
        Solleva OSError se fallisce; il temporaneo viene rimosso."""
        tmp_path = dst.with_name(dst.name + ".restore.tmp")
        try:
            shutil.copy2(src, tmp_path)
            tmp_path.replace(dst)
        except OSError:
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except OSError:
                pass
            raise

    def _try_load(self, path: Path) -> Optional[ProjectData]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return ProjectData.from_dict(data, path.parent)
        except Exception as e:
            log.error(f"Caricamento fallito da {path.name}: {e}", exc_info=True)
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