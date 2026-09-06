# sprite_studio/sprite_utils.py
import re
from pathlib import Path
from PIL import Image

from .constants import DEFAULT_DURATION_MS, IMG_EXTENSIONS

def build_pattern(prefix: str) -> re.Pattern:
    prefix_esc = re.escape(prefix)
    return re.compile(
        rf"^{prefix_esc}([A-Za-z])([0-8])(?:([A-Za-z])([0-8]))?\.(png|jpe?g)$",
        re.IGNORECASE,
    )

def sort_sprite_files(files):
    return sorted(files, key=lambda p: p.name.lower())

def load_and_pad_images(paths, anchor='bottom'):
    imgs = []
    for p in paths:
        try:
            imgs.append(Image.open(p).convert("RGBA"))
        except Exception as e:
            print(f"Avviso: {p.name} -> {e}")
    if not imgs:
        return []
    max_w = max(i.width for i in imgs)
    max_h = max(i.height for i in imgs)
    padded = []
    for img in imgs:
        canvas = Image.new("RGBA", (max_w, max_h), (0,0,0,0))
        x = (max_w - img.width)//2
        if anchor == 'bottom':
            y = max_h - img.height
        elif anchor == 'top':
            y = 0
        else:
            y = (max_h - img.height)//2
        canvas.paste(img, (x, y), img)
        padded.append(canvas)
    return padded

def export_animation(frames, out_path, fmt, durations_ms, loop=True):
    if not frames:
        raise ValueError("Nessun frame")
    if len(durations_ms) != len(frames):
        durations_ms = [durations_ms[0]] * len(frames) if durations_ms else [100]*len(frames)
    loop_count = 0 if loop else 1
    if fmt == "APNG":
        frames[0].save(
            out_path, save_all=True, append_images=frames[1:],
            duration=durations_ms, loop=loop_count, disposal=2
        )
    elif fmt == "GIF":
        gif_frames = []
        for f in frames:
            quant = f.convert("RGBA")
            alpha = quant.split()[-1]
            mask = alpha.point(lambda a: 255 if a > 127 else 0)
            rgb = quant.convert("RGB")
            pal = rgb.convert("P", palette=Image.ADAPTIVE, colors=255)
            pal.paste(255, mask=Image.eval(mask, lambda a: 255 - a))
            gif_frames.append(pal)
        gif_frames[0].save(
            out_path, save_all=True, append_images=gif_frames[1:],
            duration=durations_ms, loop=loop_count, disposal=2,
            transparency=255
        )
    else:
        raise ValueError(f"Formato non supportato: {fmt}")