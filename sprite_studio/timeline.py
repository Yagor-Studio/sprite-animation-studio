# sprite_studio/timeline.py
from pathlib import Path
from typing import List, Optional
from PIL import Image

from .models import AnimationData, FrameGroup, AngleData
from .constants import DEFAULT_DURATION_MS, TICK_MS

class TimelineModel:
    def __init__(self):
        self.frames: List[FrameGroup] = []
        self.current_angle: int = 1
        self._total_duration = 0

    def load_from_animation(self, anim: AnimationData, project_root: Path):
        self.frames = []
        for frame_group in anim.frames:
            new_group = FrameGroup(
                letter=frame_group.letter,
                duration_ms=frame_group.duration_ms
            )
            for angle_data in frame_group.angles:
                p = Path(angle_data.file)
                if not p.is_absolute():
                    p = project_root / p
                if p.exists():
                    new_group.angles.append(AngleData(
                        angle=angle_data.angle,
                        file=str(p),
                        duration_ms=angle_data.duration_ms,
                        mirrored=angle_data.mirrored
                    ))
            self.frames.append(new_group)

        self._calc_total()
        if self.frames:
            self._load_images_for_angle(self.current_angle)

    def _load_images_for_angle(self, angle: int):
        for frame_group in self.frames:
            for angle_data in frame_group.angles:
                if angle_data.angle == angle:
                    try:
                        img = Image.open(angle_data.file).convert("RGBA")
                        if angle_data.mirrored:
                            img = img.transpose(Image.FLIP_LEFT_RIGHT)
                        angle_data.image = img
                    except:
                        angle_data.image = None
                    break

    def get_frame_count(self) -> int:
        return len(self.frames)

    def set_angle(self, angle: int):
        if angle < 1 or angle > 8:
            return
        if angle != self.current_angle:
            self.current_angle = angle
            self._load_images_for_angle(angle)

    def get_frame_image(self, frame_idx: int):
        if 0 <= frame_idx < len(self.frames):
            frame = self.frames[frame_idx]
            for angle_data in frame.angles:
                if angle_data.angle == self.current_angle:
                    return angle_data.image
        return None

    def get_frame_duration(self, frame_idx: int) -> int:
        if 0 <= frame_idx < len(self.frames):
            frame = self.frames[frame_idx]
            for angle_data in frame.angles:
                if angle_data.angle == self.current_angle:
                    return angle_data.duration_ms
            return frame.duration_ms
        return DEFAULT_DURATION_MS

    def get_frame_letter(self, frame_idx: int) -> str:
        if 0 <= frame_idx < len(self.frames):
            return self.frames[frame_idx].letter
        return ""

    def _calc_total(self):
        self._total_duration = sum(self.get_frame_duration(i) for i in range(len(self.frames)))

    def get_total_ms(self):
        return self._total_duration

    def get_total_ticks(self):
        return int(self._total_duration / TICK_MS + 0.5)

    def get_total_seconds(self):
        return self._total_duration / 1000.0

    def set_duration(self, index, ms):
        if 0 <= index < len(self.frames):
            self.frames[index].duration_ms = max(1, int(ms))
            self._calc_total()

    def move_frame(self, from_idx, to_idx):
        if from_idx == to_idx or not self.frames:
            return
        self.frames.insert(to_idx, self.frames.pop(from_idx))
        self._calc_total()

    def delete_frame(self, idx):
        if 0 <= idx < len(self.frames):
            del self.frames[idx]
            self._calc_total()

    def clear(self):
        self.frames.clear()
        self._total_duration = 0