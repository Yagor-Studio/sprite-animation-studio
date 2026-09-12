# sprite_studio/project_manager.py
import json
from pathlib import Path
from datetime import datetime
from typing import List, Optional

from .constants import RECENT_FILE, PROJECT_EXTENSION
from .models import ProjectData

class ProjectManager:
    def __init__(self):
        self.current_project: Optional[ProjectData] = None
        self._load_recent()

    def create_project(self, root_path: Path, name: str, mode: str = "DooMod") -> ProjectData:
        project_path = root_path / name
        project_path.mkdir(parents=True, exist_ok=True)
        project = ProjectData(
            name=name,
            root_path=project_path,
            created=datetime.now().isoformat(),
            mode=mode,
            profiles=[]
        )
        self.current_project = project
        self._save_project()
        self._add_recent(project_path / f"{name}{PROJECT_EXTENSION}")
        return project

    def _save_project(self) -> bool:
        if not self.current_project:
            return False
        sas_path = self.current_project.root_path / f"{self.current_project.name}{PROJECT_EXTENSION}"
        try:
            with open(sas_path, 'w') as f:
                json.dump(self.current_project.to_dict(), f, indent=2)
            return True
        except Exception as e:
            print(f"Errore salvataggio: {e}")
            return False

    def load_project(self, sas_path: Path) -> Optional[ProjectData]:
        if not sas_path.exists():
            return None
        try:
            with open(sas_path, 'r') as f:
                data = json.load(f)
            project = ProjectData.from_dict(data, sas_path.parent)
            self.current_project = project
            self._add_recent(sas_path)
            return project
        except Exception as e:
            print(f"Errore caricamento: {e}")
            return None

    def _load_recent(self):
        self.recent_projects: List[Path] = []
        if RECENT_FILE.exists():
            try:
                with open(RECENT_FILE, 'r') as f:
                    data = json.load(f)
                    self.recent_projects = [Path(p) for p in data.get("recent", []) if Path(p).exists()]
            except Exception:
                pass

    def _add_recent(self, path: Path):
        if path in self.recent_projects:
            self.recent_projects.remove(path)
        self.recent_projects.insert(0, path)
        if len(self.recent_projects) > 10:
            self.recent_projects = self.recent_projects[:10]
        self._save_recent()

    def _save_recent(self):
        try:
            with open(RECENT_FILE, 'w') as f:
                json.dump({"recent": [str(p) for p in self.recent_projects]}, f, indent=2)
        except Exception:
            pass

    def get_recent(self) -> List[Path]:
        return self.recent_projects