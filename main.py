#!/usr/bin/env python3
"""
Sprite Animation Studio v0.7 - Profili multipli, navigazione funzionante
COMPLETO e FUNZIONANTE
"""

import json
import re
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from pathlib import Path
import shutil

try:
    from PIL import Image, ImageTk
except ImportError:
    print("ERRORE: Pillow non installato. Esegui: pip install pillow")
    sys.exit(1)

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False

IMG_EXTENSIONS = (".png", ".jpg", ".jpeg")
CONFIG_FILE = Path(__file__).parent / "sprite_config.json"
PROFILES_DIR = Path(__file__).parent / "profiles"
PROFILES_DIR.mkdir(exist_ok=True)

DEFAULT_DURATION_MS = 120
TICK_MS = 28

# ---------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------

def build_pattern(prefix: str) -> re.Pattern:
    prefix_esc = re.escape(prefix)
    return re.compile(
        rf"^{prefix_esc}([A-Za-z])([0-8])(?:([A-Za-z])([0-8]))?\.(png|jpe?g)$",
        re.IGNORECASE,
    )

def is_valid_code(code) -> bool:
    if not code:
        return False
    return 1 <= len(code) <= 6 and code.isalnum()

def sort_sprite_files(files, prefix: str = ''):
    pattern = build_pattern(prefix) if prefix else None
    def key(p):
        if pattern:
            m = pattern.match(p.name)
            if m:
                g = m.groups()
                l1, n1 = g[0].upper(), g[1]
                if g[2] is not None and g[3] is not None:
                    l2, n2 = g[2].upper(), g[3]
                    return (l1, n1, l2, n2)
                else:
                    return (l1, n1, '', '')
        return (p.name.lower(), '', '', '')
    return sorted(files, key=key)

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

# ---------------------------------------------------------------------
# Modello dati: Profilo → Animazioni
# ---------------------------------------------------------------------

class AnimationData:
    def __init__(self, name="", code="", file_paths=None, durations=None):
        self.name = name
        self.code = code.upper()
        self.file_paths = file_paths if file_paths is not None else []
        self.durations = durations if durations is not None else []

    def to_dict(self):
        rel_paths = []
        for p in self.file_paths:
            try:
                rel = p.relative_to(PROFILES_DIR.parent)
            except ValueError:
                rel = p
            rel_paths.append(str(rel))
        return {
            "name": self.name,
            "code": self.code,
            "files": rel_paths,
            "durations": self.durations
        }

    @classmethod
    def from_dict(cls, data, base_dir):
        paths = []
        for rel in data.get("files", []):
            p = Path(rel)
            if not p.is_absolute():
                p = base_dir / p
            if p.exists():
                paths.append(p)
        return cls(
            name=data.get("name", ""),
            code=data.get("code", ""),
            file_paths=paths,
            durations=data.get("durations", [])
        )

class ProfileData:
    def __init__(self, name="", code="", anim_type="", animations=None, file_path=None):
        self.name = name
        self.code = code.upper()
        self.type = anim_type
        self.animations = animations if animations is not None else []
        self.file_path = file_path

    def to_dict(self):
        return {
            "name": self.name,
            "code": self.code,
            "type": self.type,
            "animations": [a.to_dict() for a in self.animations]
        }

    @classmethod
    def from_dict(cls, data, base_dir, file_path=None):
        anims = []
        for a_data in data.get("animations", []):
            anim = AnimationData.from_dict(a_data, base_dir)
            anims.append(anim)
        return cls(
            name=data.get("name", ""),
            code=data.get("code", ""),
            anim_type=data.get("type", ""),
            animations=anims,
            file_path=file_path
        )

    def save(self):
        if self.file_path:
            with open(self.file_path, 'w') as f:
                json.dump(self.to_dict(), f, indent=2)
            return True
        return False

# ---------------------------------------------------------------------
# Timeline Model
# ---------------------------------------------------------------------

class TimelineModel:
    def __init__(self):
        self.frames = []
        self.file_paths = []
        self.durations_ms = []
        self._total_duration = 0

    def load_from_paths(self, paths, anchor='bottom'):
        imgs = load_and_pad_images(paths, anchor)
        self.frames = imgs
        self.file_paths = paths
        self.durations_ms = [DEFAULT_DURATION_MS] * len(imgs)
        self._calc_total()

    def load_from_animation(self, anim: AnimationData, anchor='bottom'):
        self.load_from_paths(anim.file_paths, anchor)
        if len(self.durations_ms) == len(anim.durations):
            self.durations_ms = anim.durations[:]
            self._calc_total()

    def to_animation(self, name, code):
        return AnimationData(
            name=name,
            code=code,
            file_paths=self.file_paths[:],
            durations=self.durations_ms[:]
        )

    def _calc_total(self):
        self._total_duration = sum(self.durations_ms)

    def get_total_ms(self):
        return self._total_duration

    def get_total_ticks(self):
        return int(self._total_duration / TICK_MS + 0.5)

    def get_total_seconds(self):
        return self._total_duration / 1000.0

    def set_duration(self, index, ms):
        if 0 <= index < len(self.durations_ms):
            self.durations_ms[index] = max(1, int(ms))
            self._calc_total()

    def move_frame(self, from_idx, to_idx):
        if from_idx == to_idx or not self.frames:
            return
        self.frames.insert(to_idx, self.frames.pop(from_idx))
        self.file_paths.insert(to_idx, self.file_paths.pop(from_idx))
        self.durations_ms.insert(to_idx, self.durations_ms.pop(from_idx))
        self._calc_total()

    def delete_frame(self, idx):
        if 0 <= idx < len(self.frames):
            del self.frames[idx]
            del self.file_paths[idx]
            del self.durations_ms[idx]
            self._calc_total()

    def clear(self):
        self.frames.clear()
        self.file_paths.clear()
        self.durations_ms.clear()
        self._total_duration = 0

# ---------------------------------------------------------------------
# GUI principale
# ---------------------------------------------------------------------

class SpriteStudioApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Sprite Animation Studio v0.7")
        self.root.geometry("1100x720")
        self.root.minsize(1000, 600)
        self.root.configure(bg='white')

        self.config = self._load_config()

        self.mode = tk.StringVar(value="code")
        self.code_var = tk.StringVar()
        self.folder_var = tk.StringVar(value=str(Path.cwd()))
        self.manual_files = []

        self.out_folder_var = tk.StringVar(value=self.config.get('out_folder', str(Path.cwd())))
        self.out_name_var = tk.StringVar(value="sprite_anim")
        self.format_var = tk.StringVar(value=self.config.get('format', 'APNG'))
        self.loop_var = tk.BooleanVar(value=True)
        self.anchor_var = tk.StringVar(value=self.config.get('anchor', 'bottom'))

        self.timeline = TimelineModel()
        self.current_frame_idx = 0
        self.is_playing = False
        self._after_id = None

        # Profili multipli
        self.profiles = []
        self.selected_profile_index = -1
        self.selected_animation_index = -1
        self.tree_item_to_profile = {}

        # Autocomplete
        self.autocomplete_list = []
        self.autocomplete_popup = None
        self.autocomplete_listbox = None
        self.autocomplete_selected_index = -1

        # Drag & drop
        self.drag_start_index = None
        self.drag_current_index = None
        self.selected_thumb_index = -1

        self._build_ui()
        self._update_autocomplete_list()
        self._refresh_tree()
        self._bind_global_keys()

    # -------------------- Config --------------------

    def _load_config(self):
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {}

    def _save_config(self):
        self.config['out_folder'] = self.out_folder_var.get()
        self.config['format'] = self.format_var.get()
        self.config['anchor'] = self.anchor_var.get()
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.config, f, indent=2)
        except:
            pass

    # -------------------- UI Build --------------------

    def _build_ui(self):
        main_pane = ttk.PanedWindow(self.root, orient='horizontal')
        main_pane.pack(fill='both', expand=True, padx=5, pady=5)

        # ---- Pannello sinistro ----
        left_frame = ttk.Frame(main_pane, width=250)
        main_pane.add(left_frame, weight=0)

        ttk.Label(left_frame, text="Profili / Animazioni", font=('Segoe UI', 12, 'bold')).pack(pady=(5,0))

        self.tree = ttk.Treeview(left_frame, columns=('type',), show='tree', height=12)
        self.tree.pack(fill='both', expand=True, padx=5, pady=5)
        self.tree.bind('<<TreeviewSelect>>', self._on_tree_select)

        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill='x', padx=5, pady=2)

        ttk.Button(btn_frame, text="Nuovo Profilo", command=self._new_profile).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="Carica Profilo", command=self._load_profile_from_file).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="Salva Profilo", command=self._save_profile).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="Elimina", command=self._delete_selected).pack(side='left', padx=2)

        btn_frame2 = ttk.Frame(left_frame)
        btn_frame2.pack(fill='x', padx=5, pady=2)
        ttk.Button(btn_frame2, text="Nuova Animazione", command=self._new_animation).pack(side='left', padx=2)
        ttk.Button(btn_frame2, text="Rinomina", command=self._rename_selected).pack(side='left', padx=2)

        # ---- Pannello destro ----
        right_frame = ttk.Frame(main_pane)
        main_pane.add(right_frame, weight=1)

        if DND_AVAILABLE:
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind('<<Drop>>', self._on_drop_global)

        # ----- 1. Sorgente -----
        src_frame = ttk.LabelFrame(right_frame, text="1. Fonte sprite")
        src_frame.pack(fill='x', padx=5, pady=5)

        rb_code = ttk.Radiobutton(src_frame, text="Codice", variable=self.mode, value="code", command=self._on_mode_change)
        rb_folder = ttk.Radiobutton(src_frame, text="Cartella", variable=self.mode, value="folder", command=self._on_mode_change)
        rb_manual = ttk.Radiobutton(src_frame, text="Manuale", variable=self.mode, value="manual", command=self._on_mode_change)

        rb_code.grid(row=0, column=0, sticky='w', padx=5, pady=2)
        rb_folder.grid(row=1, column=0, sticky='w', padx=5, pady=2)
        rb_manual.grid(row=2, column=0, sticky='w', padx=5, pady=2)

        self.code_frame = ttk.Frame(src_frame)
        ttk.Label(self.code_frame, text="Prefisso:").pack(side='left')
        self.code_entry = ttk.Entry(self.code_frame, textvariable=self.code_var, width=10)
        self.code_entry.pack(side='left', padx=5)
        self.code_entry.bind('<KeyRelease>', self._on_code_change)
        self.code_entry.bind('<Down>', self._on_arrow_down)
        self.code_entry.bind('<Up>', self._on_arrow_up)
        self.code_entry.bind('<Return>', self._on_enter)
        self.code_entry.bind('<Tab>', self._on_tab)
        self.code_entry.bind('<Escape>', self._close_autocomplete)
        self.suggest_btn = ttk.Button(self.code_frame, text="▼", width=3, command=self._show_suggestions)
        self.suggest_btn.pack(side='left', padx=2)
        ttk.Button(self.code_frame, text="Scegli cartella...", command=self._pick_code_folder).pack(side='left', padx=5)
        self.code_folder_lbl = ttk.Label(self.code_frame, text="(nessuna)", foreground='#666')
        self.code_folder_lbl.pack(side='left', padx=5)

        self.folder_frame = ttk.Frame(src_frame)
        ttk.Button(self.folder_frame, text="Scegli cartella...", command=self._pick_merge_folder).pack(side='left')
        self.folder_lbl = ttk.Label(self.folder_frame, text="(nessuna)", foreground='#666')
        self.folder_lbl.pack(side='left', padx=5)
        self.folder_filter_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.folder_frame, text="Filtra per prefisso", variable=self.folder_filter_var, command=self._on_mode_change).pack(side='left', padx=5)
        self.folder_code_entry = ttk.Entry(self.folder_frame, textvariable=self.code_var, width=8)
        self.folder_code_entry.pack(side='left')

        self.manual_frame = ttk.Frame(src_frame)
        ttk.Button(self.manual_frame, text="Aggiungi immagini...", command=self._add_manual_files).pack(side='left')
        ttk.Button(self.manual_frame, text="Svuota", command=self._clear_manual).pack(side='left', padx=5)
        self.manual_count_lbl = ttk.Label(self.manual_frame, text="0 file", foreground='#666')
        self.manual_count_lbl.pack(side='left', padx=5)

        self.code_frame.grid(row=0, column=1, sticky='w', padx=5, pady=3)
        self.folder_frame.grid(row=1, column=1, sticky='w', padx=5, pady=3)
        self.manual_frame.grid(row=2, column=1, sticky='w', padx=5, pady=3)
        src_frame.columnconfigure(1, weight=1)

        load_frame = ttk.Frame(right_frame)
        load_frame.pack(fill='x', padx=5, pady=5)
        ttk.Button(load_frame, text="Carica frame", command=self.load_frames).pack(side='left')
        self.status_lbl = ttk.Label(load_frame, text="Nessun frame caricato", foreground='#666')
        self.status_lbl.pack(side='left', padx=15)
        ttk.Button(load_frame, text="Salva come Animazione", command=self._save_current_as_animation).pack(side='left', padx=5)
        ttk.Label(load_frame, text="(Canc per eliminare frame selezionato)").pack(side='left', padx=5)

        # ----- 2. Timeline -----
        timeline_frame = ttk.LabelFrame(right_frame, text="2. Timeline e anteprima")
        timeline_frame.pack(fill='both', expand=True, padx=5, pady=5)

        self.canvas = tk.Canvas(timeline_frame, bg='#eee', height=160, highlightthickness=0)
        self.canvas.pack(fill='both', expand=True, padx=5, pady=5)

        player_controls = ttk.Frame(timeline_frame)
        player_controls.pack(fill='x', padx=5, pady=5)

        self.play_btn = ttk.Button(player_controls, text="▶ Play", width=8, command=self._play)
        self.play_btn.pack(side='left')
        self.pause_btn = ttk.Button(player_controls, text="⏸ Pausa", width=8, command=self._pause)
        self.pause_btn.pack(side='left', padx=3)
        self.stop_btn = ttk.Button(player_controls, text="⏹ Stop", width=8, command=self._stop)
        self.stop_btn.pack(side='left', padx=3)
        ttk.Checkbutton(player_controls, text="Loop", variable=self.loop_var).pack(side='left', padx=10)

        ttk.Label(player_controls, text="Ancora:").pack(side='left', padx=(15,3))
        anchor_combo = ttk.Combobox(player_controls, textvariable=self.anchor_var, values=['bottom','center','top'], width=8, state='readonly')
        anchor_combo.pack(side='left')
        anchor_combo.bind('<<ComboboxSelected>>', lambda e: self._on_anchor_change())

        ttk.Label(player_controls, text="Vel. base (ms):").pack(side='left', padx=(15,3))
        self.speed_spin = ttk.Spinbox(player_controls, from_=20, to=2000, increment=10, width=6, textvariable=tk.IntVar(value=DEFAULT_DURATION_MS))
        self.speed_spin.pack(side='left')
        self.speed_spin.bind('<KeyRelease>', self._on_speed_change)

        self.time_info_lbl = ttk.Label(player_controls, text="0s 0ms 0tick", foreground='#666')
        self.time_info_lbl.pack(side='right', padx=10)

        timeline_toolbar = ttk.Frame(timeline_frame)
        timeline_toolbar.pack(fill='x', padx=5, pady=3)
        ttk.Label(timeline_toolbar, text="Frame:").pack(side='left')
        self.frame_count_lbl = ttk.Label(timeline_toolbar, text="0", foreground='#666')
        self.frame_count_lbl.pack(side='left', padx=5)

        self.thumb_canvas = tk.Canvas(timeline_frame, bg='#f0f0f0', height=80, highlightthickness=0)
        self.thumb_canvas.pack(fill='x', padx=5, pady=5)
        self.thumb_refs = []
        self._bind_thumb_events()

        # ----- 3. Esportazione -----
        export_frame = ttk.LabelFrame(right_frame, text="3. Esporta animazione")
        export_frame.pack(fill='x', padx=5, pady=5)

        row1 = ttk.Frame(export_frame)
        row1.pack(fill='x', padx=5, pady=5)

        ttk.Label(row1, text="Cartella:").pack(side='left')
        out_entry = ttk.Entry(row1, textvariable=self.out_folder_var, width=30)
        out_entry.pack(side='left', padx=3, fill='x', expand=True)
        ttk.Button(row1, text="Sfoglia...", command=self._pick_output_folder).pack(side='left', padx=3)

        ttk.Label(row1, text="Nome:").pack(side='left', padx=(10,3))
        name_entry = ttk.Entry(row1, textvariable=self.out_name_var, width=15)
        name_entry.pack(side='left', padx=3)

        self.export_btn = ttk.Button(row1, text="▶ Esporta", command=self.export_animation)
        self.export_btn.pack(side='right', padx=5)

        row2 = ttk.Frame(export_frame)
        row2.pack(fill='x', padx=5, pady=5)
        ttk.Radiobutton(row2, text="APNG (alpha completo)", variable=self.format_var, value="APNG").pack(side='left', padx=5)
        ttk.Radiobutton(row2, text="GIF (compatibilità)", variable=self.format_var, value="GIF").pack(side='left', padx=5)

        self._on_mode_change()

    # -------------------- Key bindings --------------------

    def _bind_global_keys(self):
        self.root.bind('<Delete>', lambda e: self._delete_selected_frame())
        self.root.bind('<BackSpace>', lambda e: self._delete_selected_frame())

    # -------------------- Treeview e gestione profili/animazioni --------------------

    def _refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        self.tree_item_to_profile = {}

        for p_idx, profile in enumerate(self.profiles):
            profile_text = f"{profile.name} [{profile.code}]"
            profile_id = self.tree.insert("", "end", text=profile_text, values=(profile.type,))
            self.tree.item(profile_id, open=True)
            self.tree_item_to_profile[profile_id] = (p_idx, -1)

            for a_idx, anim in enumerate(profile.animations):
                anim_text = f"  {anim.name} [{anim.code}]"
                anim_id = self.tree.insert(profile_id, "end", text=anim_text, values=("anim",))
                self.tree_item_to_profile[anim_id] = (p_idx, a_idx)

        if self.selected_profile_index >= 0 and self.selected_profile_index < len(self.profiles):
            for item_id, (p_idx, a_idx) in self.tree_item_to_profile.items():
                if p_idx == self.selected_profile_index and a_idx == self.selected_animation_index:
                    self.tree.selection_set(item_id)
                    self.tree.focus(item_id)
                    break

    def _get_item_data(self, item_id):
        return self.tree_item_to_profile.get(item_id, (-1, -1))

    def _on_tree_select(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        item = sel[0]
        p_idx, a_idx = self._get_item_data(item)
        if p_idx < 0 or p_idx >= len(self.profiles):
            return

        if a_idx >= 0:
            profile = self.profiles[p_idx]
            if a_idx < len(profile.animations):
                self.selected_profile_index = p_idx
                self.selected_animation_index = a_idx
                self._load_animation(p_idx, a_idx)
        else:
            self.selected_profile_index = p_idx
            self.selected_animation_index = -1
            if p_idx < len(self.profiles):
                self.status_lbl.config(text=f"Profilo selezionato: {self.profiles[p_idx].name}")

    def _load_animation(self, profile_idx, anim_idx):
        if profile_idx < 0 or profile_idx >= len(self.profiles):
            return
        profile = self.profiles[profile_idx]
        if anim_idx < 0 or anim_idx >= len(profile.animations):
            return
        anim = profile.animations[anim_idx]
        self.timeline.load_from_animation(anim, self.anchor_var.get())
        self.current_frame_idx = 0
        self.selected_thumb_index = -1
        self._update_display()
        self.status_lbl.config(text=f"Animazione caricata: {anim.name} ({len(self.timeline.frames)} frame)")

    def _new_profile(self):
        name = simpledialog.askstring("Nuovo Profilo", "Inserisci il nome del profilo:")
        if not name:
            return
        code = simpledialog.askstring("Codice Profilo", "Inserisci il codice di 2 caratteri (es. CA):")
        if not code or len(code) != 2 or not code.isalnum():
            messagebox.showwarning("Attenzione", "Il codice deve essere di 2 caratteri alfanumerici.")
            return
        code = code.upper()
        tipo = simpledialog.askstring("Tipo", "Inserisci il tipo (es. HUD, Monster):", initialvalue="HUD")
        if tipo is None:
            tipo = ""

        profile = ProfileData(name=name, code=code, anim_type=tipo, animations=[])
        self.profiles.append(profile)
        self.selected_profile_index = len(self.profiles) - 1
        self.selected_animation_index = -1
        self.timeline.clear()
        self._refresh_tree()
        self._update_display()
        self.status_lbl.config(text=f"Nuovo profilo: {name}")

    def _save_profile(self):
        if self.selected_profile_index < 0 or self.selected_profile_index >= len(self.profiles):
            messagebox.showwarning("Attenzione", "Nessun profilo selezionato.")
            return
        profile = self.profiles[self.selected_profile_index]

        if self.timeline.frames and self.selected_animation_index >= 0:
            if messagebox.askyesno("Salva animazione", "Salvare l'animazione corrente nel profilo prima di salvare il profilo?"):
                self._save_current_as_animation()

        filename = f"{profile.name}_{profile.code}.spriteprofile"
        filepath = PROFILES_DIR / filename
        profile.file_path = filepath
        data = profile.to_dict()
        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            self.status_lbl.config(text=f"Profilo salvato: {filepath.name}")
            messagebox.showinfo("Fatto", f"Profilo salvato in:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Errore", f"Salvataggio fallito: {e}")

    def _load_profile_from_file(self):
        file_path = filedialog.askopenfilename(
            title="Carica profilo",
            filetypes=[("Sprite Profile", "*.spriteprofile")],
            initialdir=PROFILES_DIR
        )
        if not file_path:
            return
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            profile = ProfileData.from_dict(data, PROFILES_DIR, Path(file_path))
            self.profiles.append(profile)
            self.selected_profile_index = len(self.profiles) - 1
            self.selected_animation_index = -1
            self.timeline.clear()
            self._refresh_tree()
            self._update_display()
            self.status_lbl.config(text=f"Profilo caricato: {profile.name}")
        except Exception as e:
            messagebox.showerror("Errore", f"Caricamento fallito: {e}")

    def _delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        item = sel[0]
        p_idx, a_idx = self._get_item_data(item)

        if p_idx < 0 or p_idx >= len(self.profiles):
            return

        if a_idx >= 0:
            profile = self.profiles[p_idx]
            if a_idx < len(profile.animations):
                anim_name = profile.animations[a_idx].name
                if messagebox.askyesno("Conferma", f"Eliminare l'animazione '{anim_name}'?"):
                    del profile.animations[a_idx]
                    if self.selected_profile_index == p_idx and self.selected_animation_index == a_idx:
                        self.selected_animation_index = -1
                        self.timeline.clear()
                        self._update_display()
                    self._refresh_tree()
                    self.status_lbl.config(text=f"Animazione '{anim_name}' eliminata")
        else:
            profile = self.profiles[p_idx]
            if messagebox.askyesno("Conferma", f"Eliminare il profilo '{profile.name}'?"):
                del self.profiles[p_idx]
                if self.selected_profile_index == p_idx:
                    self.selected_profile_index = -1
                    self.selected_animation_index = -1
                    self.timeline.clear()
                    self._update_display()
                self._refresh_tree()
                self.status_lbl.config(text=f"Profilo '{profile.name}' eliminato")

    def _rename_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        item = sel[0]
        p_idx, a_idx = self._get_item_data(item)

        if p_idx < 0 or p_idx >= len(self.profiles):
            return
        profile = self.profiles[p_idx]

        if a_idx >= 0:
            if a_idx < len(profile.animations):
                anim = profile.animations[a_idx]
                new_name = simpledialog.askstring("Rinomina animazione", "Nuovo nome:", initialvalue=anim.name)
                if new_name:
                    anim.name = new_name
                    self._refresh_tree()
                    self.status_lbl.config(text=f"Animazione rinominata in {new_name}")
        else:
            new_name = simpledialog.askstring("Rinomina profilo", "Nuovo nome:", initialvalue=profile.name)
            if new_name:
                profile.name = new_name
                self._refresh_tree()
                self.status_lbl.config(text=f"Profilo rinominato in {new_name}")

    def _new_animation(self):
        if self.selected_profile_index < 0 or self.selected_profile_index >= len(self.profiles):
            messagebox.showwarning("Attenzione", "Seleziona prima un profilo.")
            return
        profile = self.profiles[self.selected_profile_index]

        name = simpledialog.askstring("Nuova Animazione", "Inserisci il nome dell'animazione:")
        if not name:
            return
        code = simpledialog.askstring("Codice Animazione", "Inserisci il codice di 2 caratteri (es. PA):")
        if not code or len(code) != 2 or not code.isalnum():
            messagebox.showwarning("Attenzione", "Il codice deve essere di 2 caratteri alfanumerici.")
            return
        code = code.upper()

        anim = AnimationData(name=name, code=code)
        profile.animations.append(anim)
        self.selected_animation_index = len(profile.animations) - 1
        self.timeline.clear()
        self._refresh_tree()
        self._update_display()
        self.status_lbl.config(text=f"Nuova animazione: {name} (vuota)")

    def _save_current_as_animation(self):
        if self.selected_profile_index < 0 or self.selected_profile_index >= len(self.profiles):
            messagebox.showwarning("Attenzione", "Seleziona prima un profilo.")
            return
        if not self.timeline.frames:
            messagebox.showwarning("Attenzione", "Nessun frame da salvare.")
            return

        profile = self.profiles[self.selected_profile_index]

        if self.selected_animation_index >= 0 and self.selected_animation_index < len(profile.animations):
            anim = profile.animations[self.selected_animation_index]
            if messagebox.askyesno("Conferma", f"Sovrascrivere l'animazione '{anim.name}' con la timeline corrente?"):
                new_anim = self.timeline.to_animation(anim.name, anim.code)
                profile.animations[self.selected_animation_index] = new_anim
                self._refresh_tree()
                self.status_lbl.config(text=f"Animazione '{anim.name}' aggiornata")
                return

        name = simpledialog.askstring("Nome Animazione", "Inserisci il nome della nuova animazione:")
        if not name:
            return
        code = simpledialog.askstring("Codice Animazione", "Inserisci il codice di 2 caratteri:", initialvalue="AA")
        if not code or len(code) != 2 or not code.isalnum():
            messagebox.showwarning("Attenzione", "Codice non valido.")
            return
        code = code.upper()

        new_anim = self.timeline.to_animation(name, code)
        profile.animations.append(new_anim)
        self.selected_animation_index = len(profile.animations) - 1
        self._refresh_tree()
        self.status_lbl.config(text=f"Nuova animazione '{name}' salvata")

    # -------------------- Autocomplete --------------------

    def _update_autocomplete_list(self):
        folder = self.folder_var.get().strip()
        if not folder:
            self.autocomplete_list = []
            return
        try:
            paths = list(Path(folder).iterdir())
            prefixes = set()
            for p in paths:
                if p.is_file() and p.suffix.lower() in IMG_EXTENSIONS:
                    name = p.stem
                    if len(name) >= 4:
                        prefixes.add(name[:4])
            self.autocomplete_list = sorted(prefixes)
        except:
            self.autocomplete_list = []

    def _on_code_change(self, event=None):
        self._show_suggestions()

    def _show_suggestions(self):
        prefix = self.code_var.get().upper()
        matches = [p for p in self.autocomplete_list if p.startswith(prefix)] if prefix else []
        if not matches:
            self._close_autocomplete()
            return
        if self.autocomplete_popup and self.autocomplete_popup.winfo_exists():
            self.autocomplete_listbox.delete(0, tk.END)
            for m in matches:
                self.autocomplete_listbox.insert(tk.END, m)
            self.autocomplete_selected_index = -1
            self._position_popup()
            return
        popup = tk.Toplevel(self.root)
        popup.wm_overrideredirect(True)
        popup.configure(bg='white', relief='solid', bd=1)
        popup.takefocus = False
        listbox = tk.Listbox(popup, height=min(6, len(matches)), font=('Segoe UI', 10), selectmode='single', takefocus=False)
        listbox.pack(fill='both', expand=True)
        for m in matches:
            listbox.insert(tk.END, m)
        self.autocomplete_popup = popup
        self.autocomplete_listbox = listbox
        self.autocomplete_selected_index = -1
        self._position_popup()
        listbox.bind('<Double-Button-1>', lambda e: self._select_autocomplete())
        listbox.bind('<Button-1>', self._on_listbox_click)

    def _position_popup(self):
        if not self.autocomplete_popup or not self.autocomplete_popup.winfo_exists():
            return
        x = self.code_entry.winfo_rootx()
        y = self.code_entry.winfo_rooty() + self.code_entry.winfo_height()
        self.autocomplete_popup.geometry(f"+{x}+{y}")

    def _on_arrow_down(self, event):
        if self.autocomplete_popup and self.autocomplete_popup.winfo_exists():
            size = self.autocomplete_listbox.size()
            if size > 0:
                idx = self.autocomplete_selected_index + 1
                if idx >= size:
                    idx = 0
                self.autocomplete_listbox.selection_clear(0, tk.END)
                self.autocomplete_listbox.selection_set(idx)
                self.autocomplete_listbox.see(idx)
                self.autocomplete_selected_index = idx
            return "break"

    def _on_arrow_up(self, event):
        if self.autocomplete_popup and self.autocomplete_popup.winfo_exists():
            size = self.autocomplete_listbox.size()
            if size > 0:
                idx = self.autocomplete_selected_index - 1
                if idx < 0:
                    idx = size - 1
                self.autocomplete_listbox.selection_clear(0, tk.END)
                self.autocomplete_listbox.selection_set(idx)
                self.autocomplete_listbox.see(idx)
                self.autocomplete_selected_index = idx
            return "break"

    def _on_enter(self, event):
        if self.autocomplete_popup and self.autocomplete_popup.winfo_exists():
            if self.autocomplete_selected_index >= 0:
                self._select_autocomplete()
                return "break"
        self.load_frames()
        return "break"

    def _on_tab(self, event):
        if self.autocomplete_popup and self.autocomplete_popup.winfo_exists():
            if self.autocomplete_selected_index < 0:
                self.autocomplete_selected_index = 0
                self.autocomplete_listbox.selection_clear(0, tk.END)
                self.autocomplete_listbox.selection_set(0)
            self._select_autocomplete()
            return "break"

    def _on_listbox_click(self, event):
        idx = self.autocomplete_listbox.nearest(event.y)
        if idx >= 0:
            self.autocomplete_listbox.selection_clear(0, tk.END)
            self.autocomplete_listbox.selection_set(idx)
            self.autocomplete_selected_index = idx
            self._select_autocomplete()

    def _select_autocomplete(self):
        if self.autocomplete_popup and self.autocomplete_popup.winfo_exists():
            idx = self.autocomplete_selected_index
            if idx >= 0:
                value = self.autocomplete_listbox.get(idx)
                self.code_var.set(value)
                self._close_autocomplete()

    def _close_autocomplete(self, event=None):
        if self.autocomplete_popup and self.autocomplete_popup.winfo_exists():
            self.autocomplete_popup.destroy()
        self.autocomplete_popup = None
        self.autocomplete_listbox = None
        self.autocomplete_selected_index = -1

    # -------------------- File pickers --------------------

    def _pick_code_folder(self):
        d = filedialog.askdirectory(title="Seleziona cartella sprite")
        if d:
            self.folder_var.set(d)
            self.code_folder_lbl.config(text=Path(d).name)
            self._update_autocomplete_list()

    def _pick_merge_folder(self):
        d = filedialog.askdirectory(title="Seleziona cartella")
        if d:
            self.folder_var.set(d)
            self.folder_lbl.config(text=Path(d).name)
            self._update_autocomplete_list()

    def _add_manual_files(self):
        files = filedialog.askopenfilenames(title="Seleziona immagini", filetypes=[("Immagini","*.png *.jpg *.jpeg")])
        if files:
            self.manual_files.extend(Path(f) for f in files)
            self.manual_count_lbl.config(text=f"{len(self.manual_files)} file")
            if self.mode.get() == 'manual':
                self.load_frames()

    def _clear_manual(self):
        self.manual_files.clear()
        self.manual_count_lbl.config(text="0 file")

    def _pick_output_folder(self):
        d = filedialog.askdirectory(title="Cartella destinazione")
        if d:
            self.out_folder_var.set(d)
            self._save_config()

    def _on_drop_global(self, event):
        raw = event.data
        paths = self.root.tk.splitlist(raw) if hasattr(self.root, 'tk') else raw.split()
        added = 0
        for p in paths:
            path = Path(p)
            if path.is_file() and path.suffix.lower() in IMG_EXTENSIONS:
                self.manual_files.append(path)
                added += 1
        if added:
            self.mode.set('manual')
            self._on_mode_change()
            self.manual_count_lbl.config(text=f"{len(self.manual_files)} file")
            self.load_frames()

    # -------------------- Mode switching --------------------

    def _on_mode_change(self):
        self.code_frame.grid_remove()
        self.folder_frame.grid_remove()
        self.manual_frame.grid_remove()
        m = self.mode.get()
        if m == 'code':
            self.code_frame.grid()
        elif m == 'folder':
            self.folder_frame.grid()
            self.folder_code_entry.configure(state='normal' if self.folder_filter_var.get() else 'disabled')
        else:
            self.manual_frame.grid()
        self._update_autocomplete_list()

    def _on_anchor_change(self):
        if self.timeline.frames:
            self.load_frames()

    # -------------------- Caricamento frame --------------------

    def _gather_paths(self):
        m = self.mode.get()
        prefix = self.code_var.get().strip().upper()
        if m == 'code':
            if not self.folder_var.get():
                messagebox.showwarning("Attenzione", "Scegli una cartella.")
                return []
            if len(prefix) < 4:
                messagebox.showwarning("Attenzione", "Il prefisso deve essere di almeno 4 caratteri (es. CAPA).")
                return []
            pattern = build_pattern(prefix)
            folder = Path(self.folder_var.get())
            files = [f for f in folder.iterdir() if f.is_file() and pattern.match(f.name)]
            return sort_sprite_files(files, prefix)
        elif m == 'folder':
            if not self.folder_var.get():
                messagebox.showwarning("Attenzione", "Scegli una cartella.")
                return []
            folder = Path(self.folder_var.get())
            if self.folder_filter_var.get():
                if len(prefix) < 4:
                    messagebox.showwarning("Attenzione", "Il prefisso deve essere di almeno 4 caratteri.")
                    return []
                pattern = build_pattern(prefix)
                files = [f for f in folder.iterdir() if f.is_file() and pattern.match(f.name)]
                return sort_sprite_files(files, prefix)
            else:
                files = [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in IMG_EXTENSIONS]
                return sort_sprite_files(files, '')
        else:
            if not self.manual_files:
                messagebox.showwarning("Attenzione", "Nessuna immagine selezionata.")
                return []
            if prefix:
                pattern = build_pattern(prefix)
                files = [f for f in self.manual_files if pattern.match(f.name)]
            else:
                files = self.manual_files
            return sort_sprite_files(files, prefix)

    def load_frames(self):
        self._stop()
        paths = self._gather_paths()
        if not paths:
            self.status_lbl.config(text="Nessun file trovato")
            self.timeline.clear()
            self.selected_thumb_index = -1
            self._update_display()
            return
        anchor = self.anchor_var.get()
        self.timeline.load_from_paths(paths, anchor)
        if not self.timeline.frames:
            self.status_lbl.config(text="Errore nel caricamento")
            return
        self.current_frame_idx = 0
        self.selected_thumb_index = -1
        self._update_display()
        self.status_lbl.config(text=f"{len(self.timeline.frames)} frame caricati")
        self._draw_thumbnails()

    # -------------------- Display --------------------

    def _update_display(self):
        if not self.timeline.frames:
            self.canvas.delete('all')
            self.frame_count_lbl.config(text="0")
            self.time_info_lbl.config(text="0s 0ms 0tick")
            return
        self._show_frame(self.current_frame_idx)
        self.frame_count_lbl.config(text=f"{len(self.timeline.frames)}")
        total_ms = self.timeline.get_total_ms()
        total_s = total_ms / 1000.0
        total_ticks = self.timeline.get_total_ticks()
        self.time_info_lbl.config(text=f"{total_s:.2f}s  {total_ms}ms  {total_ticks}tick")
        self._draw_thumbnails()

    def _show_frame(self, idx):
        if idx < 0 or idx >= len(self.timeline.frames):
            return
        frame = self.timeline.frames[idx]
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 10:
            w = 300
        if h < 10:
            h = 160
        scale = min((w - 20)/frame.width, (h - 20)/frame.height, 4.0)
        scale = max(scale, 0.05)
        disp_w = int(frame.width * scale)
        disp_h = int(frame.height * scale)
        disp_img = frame.resize((disp_w, disp_h), Image.NEAREST)
        checker = self._make_checker(disp_w, disp_h)
        checker.paste(disp_img, (0,0), disp_img)
        self._tk_img = ImageTk.PhotoImage(checker)
        self.canvas.delete('all')
        cx, cy = w//2, h//2
        self.canvas.create_image(cx, cy, anchor='center', image=self._tk_img)

    @staticmethod
    def _make_checker(w,h,cell=8):
        base = Image.new("RGBA", (w,h), (255,255,255,255))
        c1 = (210,210,210,255); c2=(240,240,240,255)
        for y in range(0,h,cell):
            for x in range(0,w,cell):
                col = c1 if ((x//cell)+(y//cell))%2==0 else c2
                for yy in range(y,min(y+cell,h)):
                    for xx in range(x,min(x+cell,w)):
                        base.putpixel((xx,yy), col)
        return base

    # -------------------- Thumbnails --------------------

    def _bind_thumb_events(self):
        self.thumb_canvas.bind('<Button-1>', self._on_thumb_press)
        self.thumb_canvas.bind('<B1-Motion>', self._on_thumb_drag)
        self.thumb_canvas.bind('<ButtonRelease-1>', self._on_thumb_release)
        self.thumb_canvas.bind('<Leave>', self._on_thumb_leave)
        self.thumb_canvas.bind('<Button-3>', self._on_thumb_right_click)

    def _draw_thumbnails(self):
        self.thumb_canvas.delete('all')
        self.thumb_refs.clear()
        if not self.timeline.frames:
            return
        thumb_w = 50
        thumb_h = 50
        spacing = 6
        total_w = len(self.timeline.frames) * (thumb_w + spacing)
        self.thumb_canvas.config(scrollregion=(0,0,total_w,thumb_h+25))

        for i, img in enumerate(self.timeline.frames):
            thumb = img.copy()
            thumb.thumbnail((thumb_w, thumb_h), Image.NEAREST)
            tk_thumb = ImageTk.PhotoImage(thumb)
            self.thumb_refs.append(tk_thumb)
            x = i * (thumb_w + spacing)
            y = 5
            if i == self.selected_thumb_index:
                self.thumb_canvas.create_rectangle(x-2, y-2, x+thumb_w+2, y+thumb_h+2, outline='#ff0000', fill='', width=2)
            self.thumb_canvas.create_rectangle(x, y, x+thumb_w, y+thumb_h, outline='#aaa', fill='', width=1)
            self.thumb_canvas.create_image(x, y, anchor='nw', image=tk_thumb)
            dur = self.timeline.durations_ms[i] if i < len(self.timeline.durations_ms) else 0
            rect_id = self.thumb_canvas.create_rectangle(x, y, x+thumb_w, y+thumb_h, outline='', fill='', tags=(f'thumb_{i}',))
            self.thumb_canvas.tag_bind(f'thumb_{i}', '<Button-1>', lambda e, idx=i: self._on_thumb_select(idx))
            self.thumb_canvas.create_text(x+thumb_w//2, y+thumb_h+2, text=f"{dur}ms", font=('Segoe UI',7), anchor='n')

    def _on_thumb_select(self, idx):
        self.selected_thumb_index = idx
        self._draw_thumbnails()

    def _on_thumb_right_click(self, event):
        items = self.thumb_canvas.find_overlapping(event.x, event.y, event.x+1, event.y+1)
        for item in items:
            tags = self.thumb_canvas.gettags(item)
            for tag in tags:
                if tag.startswith('thumb_'):
                    idx = int(tag.split('_')[1])
                    if 0 <= idx < len(self.timeline.frames):
                        self.selected_thumb_index = idx
                        self._draw_thumbnails()
                        # Menu contestuale
                        menu = Menu(self.root, tearoff=0)
                        menu.add_command(label="Cambia durata", command=lambda: self._change_frame_duration(idx))
                        menu.add_command(label="Elimina frame", command=lambda: self._delete_frame_by_index(idx))
                        menu.post(event.x_root, event.y_root)
                        return

    def _change_frame_duration(self, idx):
        current = self.timeline.durations_ms[idx] if idx < len(self.timeline.durations_ms) else DEFAULT_DURATION_MS
        new = simpledialog.askinteger("Durata frame", f"Durata in ms per il frame {idx+1}:", initialvalue=current, minvalue=1, maxvalue=10000)
        if new is not None:
            self.timeline.set_duration(idx, new)
            self._update_display()

    def _delete_frame_by_index(self, idx):
        if 0 <= idx < len(self.timeline.frames):
            if messagebox.askyesno("Conferma", f"Eliminare il frame {idx+1}?"):
                self.timeline.delete_frame(idx)
                self.selected_thumb_index = -1
                if idx >= len(self.timeline.frames):
                    self.current_frame_idx = len(self.timeline.frames) - 1
                self._update_display()

    def _on_thumb_press(self, event):
        items = self.thumb_canvas.find_overlapping(event.x, event.y, event.x+1, event.y+1)
        for item in items:
            tags = self.thumb_canvas.gettags(item)
            for tag in tags:
                if tag.startswith('thumb_'):
                    idx = int(tag.split('_')[1])
                    if 0 <= idx < len(self.timeline.frames):
                        self.drag_start_index = idx
                        self.drag_current_index = idx
                        self.selected_thumb_index = idx
                        self._draw_thumbnails()
                        return

    def _on_thumb_drag(self, event):
        if self.drag_start_index is None:
            return
        thumb_w = 50
        spacing = 6
        x = event.x
        total_w = len(self.timeline.frames) * (thumb_w + spacing)
        if x < 0:
            target = 0
        elif x >= total_w:
            target = len(self.timeline.frames) - 1
        else:
            target = int(x // (thumb_w + spacing))
        if target != self.drag_current_index and target != self.drag_start_index:
            self.timeline.move_frame(self.drag_start_index, target)
            self.drag_start_index = target
            self.drag_current_index = target
            self.selected_thumb_index = target
            self._draw_thumbnails()
            self._update_display()

    def _on_thumb_release(self, event):
        self.drag_start_index = None
        self.drag_current_index = None
        self._draw_thumbnails()
        self._update_display()

    def _on_thumb_leave(self, event):
        self.drag_start_index = None
        self.drag_current_index = None

    def _delete_selected_frame(self):
        if self.selected_thumb_index < 0 or self.selected_thumb_index >= len(self.timeline.frames):
            return
        self._delete_frame_by_index(self.selected_thumb_index)

    # -------------------- Player --------------------

    def _play(self):
        if not self.timeline.frames:
            messagebox.showinfo("Attenzione", "Carica dei frame prima.")
            return
        if self.is_playing:
            return
        self.is_playing = True
        self._tick()

    def _pause(self):
        self.is_playing = False
        if self._after_id:
            self.root.after_cancel(self._after_id)
            self._after_id = None

    def _stop(self):
        self._pause()
        self.current_frame_idx = 0
        self._show_frame(0)

    def _tick(self):
        if not self.is_playing or not self.timeline.frames:
            return
        self._show_frame(self.current_frame_idx)
        next_idx = self.current_frame_idx + 1
        if next_idx >= len(self.timeline.frames):
            if self.loop_var.get():
                next_idx = 0
            else:
                self.is_playing = False
                return
        self.current_frame_idx = next_idx
        dur = self.timeline.durations_ms[self.current_frame_idx] if self.current_frame_idx < len(self.timeline.durations_ms) else DEFAULT_DURATION_MS
        self._after_id = self.root.after(dur, self._tick)

    def _on_speed_change(self, event=None):
        try:
            new_speed = int(self.speed_spin.get())
        except:
            return
        if self.timeline.frames:
            for i in range(len(self.timeline.durations_ms)):
                self.timeline.durations_ms[i] = max(1, new_speed)
            self.timeline._calc_total()
            self._update_display()

    # -------------------- Export --------------------

    def export_animation(self):
        if not self.timeline.frames:
            messagebox.showwarning("Attenzione", "Carica prima dei frame.")
            return
        out_folder = Path(self.out_folder_var.get())
        if not out_folder.exists():
            messagebox.showerror("Errore", "Cartella destinazione non valida.")
            return
        name = self.out_name_var.get().strip() or "sprite_anim"
        fmt = self.format_var.get()
        ext = ".png" if fmt == "APNG" else ".gif"
        out_path = out_folder / f"{name}{ext}"

        try:
            export_animation(
                self.timeline.frames,
                out_path,
                fmt,
                self.timeline.durations_ms,
                loop=self.loop_var.get()
            )
        except Exception as e:
            messagebox.showerror("Errore", f"Esportazione fallita: {e}")
            return
        messagebox.showinfo("Fatto", f"Animazione salvata in:\n{out_path}")
        self.status_lbl.config(text=f"Esportato: {out_path.name}")
        self._save_config()

# ---------------------------------------------------------------------
# Avvio
# ---------------------------------------------------------------------

def main():
    root = TkinterDnD.Tk() if DND_AVAILABLE else tk.Tk()
    app = SpriteStudioApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()