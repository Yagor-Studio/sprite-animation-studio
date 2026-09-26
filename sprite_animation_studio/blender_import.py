# sprite_animation_studio/blender_import.py
"""Conversione manifest Blender -> modelli SAS.

Riusa i modelli esistenti (ProjectData, ProfileData, AnimationData,
FrameGroup, AngleData) senza inventare strutture parallele.
"""

from pathlib import Path
from typing import Tuple, List

from .models import ProfileData, AnimationData, FrameGroup, AngleData
from .constants import DEFAULT_DURATION_MS


# ----------------------------------------------------------------------
# MANIFEST -> MODELLI
# ----------------------------------------------------------------------

def manifest_to_models(manifest: dict, project_root: Path) -> Tuple[ProfileData, AnimationData]:
    """Trasforma un manifest in (profile, anim).

    Il profile ritornato è "usa e getta": serve solo come contenitore
    per il merge col progetto. L'animazione è completa di frame/angoli.
    """
    sprite = manifest.get("sprite", {}) or {}
    anim_info = manifest.get("animation", {}) or {}

    profile_code = (sprite.get("code") or "XX").upper()[:2].ljust(2, "X")
    profile_name = sprite.get("name") or f"Sprite {profile_code}"

    anim_code = (anim_info.get("code") or "AA").upper()[:2].ljust(2, "A")
    anim_name = anim_info.get("name") or f"Animazione {anim_code}"
    loop = bool(anim_info.get("loop", True))
    anchor = anim_info.get("anchor", "bottom")

    out_dir = manifest.get("output_dir") or ""
    out_dir_path = Path(out_dir) if out_dir else None

    frames: List[FrameGroup] = []
    for f_data in manifest.get("frames", []) or []:
        letter = (f_data.get("letter") or "").strip()
        if not letter:
            continue
        raw_duration = f_data.get("duration_ms", DEFAULT_DURATION_MS)
        try:
            duration = int(raw_duration)
        except (TypeError, ValueError):
            duration = DEFAULT_DURATION_MS

        angles: List[AngleData] = []
        for a_data in f_data.get("angles", []) or []:
            try:
                angle = int(a_data.get("angle", 1))
            except (TypeError, ValueError):
                continue
            filename = a_data.get("file") or ""
            file_field = _resolve_file_field(filename, out_dir_path, project_root)
            angles.append(AngleData(
                angle=angle,
                file=file_field,
                duration_ms=duration,
                mirrored=False,
            ))

        frames.append(FrameGroup(
            letter=letter,
            angles=angles,
            duration_ms=duration,
        ))

    anim = AnimationData(
        name=anim_name,
        code=anim_code,
        frames=frames,
        loop=loop,
        anchor=anchor,
    )

    profile = ProfileData(
        name=profile_name,
        code=profile_code,
        type="HUD",
        animations=[anim],
        folder_path=out_dir,
    )

    return profile, anim


def _resolve_file_field(filename: str, out_dir: Path, project_root: Path) -> str:
    """Restituisce il percorso da salvare in AngleData.file.

    Prova a renderlo relativo al project_root; se non è possibile,
    salva il percorso assoluto (pattern già usato in ui_profile.py).
    """
    if not filename:
        return ""

    candidate = Path(filename)
    if not candidate.is_absolute() and out_dir is not None:
        candidate = out_dir / filename

    try:
        return str(candidate.relative_to(project_root))
    except ValueError:
        return str(candidate)


# ----------------------------------------------------------------------
# MERGE NEL PROGETTO
# ----------------------------------------------------------------------

def apply_manifest_to_project(project, manifest: dict, project_root: Path):
    """Crea o aggiorna profilo + animazione dentro `project`.

    Ritorna (profile, anim, action) con action in:
      full: "created_profile" | "created_anim" | "updated_anim"
      live: "created_profile" | "created_anim" | "updated_anim" | "live_updated"
    """
    new_profile, new_anim = manifest_to_models(manifest, project_root)
    kind = manifest.get("kind", "full")

    # 1) profilo
    target_profile = None
    for p in project.profiles:
        if p.code == new_profile.code:
            target_profile = p
            break
    if target_profile is None:
        project.profiles.append(new_profile)
        return new_profile, new_anim, "created_profile"

    # 2) animazione
    target_anim = None
    for i, a in enumerate(target_profile.animations):
        if a.code == new_anim.code:
            target_anim = a
            break

    if kind == "live":
        # MERGE chirurgico: sostituisci solo i frame presenti nel manifest
        if target_anim is None:
            target_profile.animations.append(new_anim)
            return target_profile, new_anim, "created_anim"

        # Mappa lettera -> indice nell'animazione esistente
        by_letter = {fg.letter: i for i, fg in enumerate(target_anim.frames)}
        for new_fg in new_anim.frames:
            if new_fg.letter in by_letter:
                target_anim.frames[by_letter[new_fg.letter]] = new_fg
            else:
                # Inserisci mantenendo l'ordine alfabetico
                target_anim.frames.append(new_fg)
                target_anim.frames.sort(key=lambda f: f.letter)
        if not target_profile.folder_path and new_profile.folder_path:
            target_profile.folder_path = new_profile.folder_path
        return target_profile, target_anim, "live_updated"

    # kind == "full": comportamento classico
    if target_anim is None:
        target_profile.animations.append(new_anim)
        if not target_profile.folder_path and new_profile.folder_path:
            target_profile.folder_path = new_profile.folder_path
        return target_profile, new_anim, "created_anim"

    # Sostituisci l'animazione intera
    for i, a in enumerate(target_profile.animations):
        if a.code == new_anim.code:
            target_profile.animations[i] = new_anim
            break
    if not target_profile.folder_path and new_profile.folder_path:
        target_profile.folder_path = new_profile.folder_path
    return target_profile, new_anim, "updated_anim"