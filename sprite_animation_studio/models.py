# sprite_studio/models.py
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Any

from .constants import DEFAULT_DURATION_MS

@dataclass
class AngleData:
    angle: int
    file: str = ""
    duration_ms: int = DEFAULT_DURATION_MS
    mirrored: bool = False
    image: Optional[Any] = field(default=None, compare=False, repr=False)

@dataclass
class FrameGroup:
    letter: str
    angles: List[AngleData] = field(default_factory=list)
    duration_ms: int = DEFAULT_DURATION_MS

    def get_angle(self, angle: int) -> Optional[AngleData]:
        for a in self.angles:
            if a.angle == angle:
                return a
        return None

    def has_angle(self, angle: int) -> bool:
        return any(a.angle == angle for a in self.angles)

@dataclass
class AnimationData:
    name: str
    code: str
    frames: List[FrameGroup] = field(default_factory=list)
    loop: bool = True
    anchor: str = "bottom"

@dataclass
class ProfileData:
    name: str
    code: str
    type: str = "HUD"
    animations: List[AnimationData] = field(default_factory=list)
    folder_path: str = ""

@dataclass
class ProjectData:
    name: str
    root_path: Path
    created: str = ""
    mode: str = "DooMod"
    profiles: List[ProfileData] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "version": "1.0",
            "project_name": self.name,
            "created": self.created,
            "mode": self.mode,
            "profiles": [
                {
                    "name": p.name,
                    "code": p.code,
                    "type": p.type,
                    "folder_path": p.folder_path,
                    "animations": [
                        {
                            "name": a.name,
                            "code": a.code,
                            "loop": a.loop,
                            "anchor": a.anchor,
                            "frames": [
                                {
                                    "letter": f.letter,
                                    "duration_ms": f.duration_ms,
                                    "angles": [
                                        {"angle": a.angle, "file": a.file, "duration_ms": a.duration_ms, "mirrored": a.mirrored}
                                        for a in f.angles
                                    ]
                                }
                                for f in a.frames
                            ]
                        }
                        for a in p.animations
                    ]
                }
                for p in self.profiles
            ]
        }

    @classmethod
    def from_dict(cls, data: dict, root_path: Path) -> "ProjectData":
        profiles = []
        for p_data in data.get("profiles", []):
            animations = []
            for a_data in p_data.get("animations", []):
                frames = []
                for f_data in a_data.get("frames", []):
                    angles = [
                        AngleData(
                            angle=ad["angle"],
                            file=ad.get("file", ""),
                            duration_ms=ad.get("duration_ms", DEFAULT_DURATION_MS),
                            mirrored=ad.get("mirrored", False)
                        )
                        for ad in f_data.get("angles", [])
                    ]
                    frames.append(FrameGroup(
                        letter=f_data["letter"],
                        angles=angles,
                        duration_ms=f_data.get("duration_ms", DEFAULT_DURATION_MS)
                    ))
                animations.append(AnimationData(
                    name=a_data["name"],
                    code=a_data["code"],
                    frames=frames,
                    loop=a_data.get("loop", True),
                    anchor=a_data.get("anchor", "bottom")
                ))
            profiles.append(ProfileData(
                name=p_data["name"],
                code=p_data["code"],
                type=p_data.get("type", "HUD"),
                folder_path=p_data.get("folder_path", ""),
                animations=animations
            ))
        return cls(
            name=data["project_name"],
            root_path=root_path,
            created=data.get("created", ""),
            mode=data.get("mode", "DooMod"),
            profiles=profiles
        )