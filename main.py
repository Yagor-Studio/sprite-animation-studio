#!/usr/bin/env python3
"""
Sprite Animation Studio - Doom-style sprite manager with interactive timeline
----------------------------------------------------------------------------
Tool per sviluppatori di sprite (stile Doom/GZDoom): raccoglie sprite,
li mostra in una timeline interattiva, regola durata per frame,
esporta in GIF/APNG con controllo tick/ms.
"""

import json
import re
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from pathlib import Path

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
DEFAULT_DURATION_MS = 120
TICK_MS = 28  # standard Doom tick ~ 28ms

# ---------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------

def build_pattern(code: str) -> re.Pattern:
    code_esc = re.escape(code)
    return re.compile(
        rf"^{code_esc}([A-Za-z])([0-8])(?:([A-Za-z])([0-8]))?\.(png|jpe?g)$",
        re.IGNORECASE,
    )

def is_valid_code(code) -> bool:
    if not code:
        return False
    return 1 <= len(code) <= 6 and code.isalnum()

def sort_sprite_files(files, code: str = ''):
    pattern = build_pattern(code) if code else None
    def key(p):
        if pattern:
            m = pattern.match(p.name)
            if m:
                g = m.groups()
                l1, n1 = g[0].upper(), g[1]
                # seconda coppia opzionale
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
        else:  # center
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
# Timeline Model
# ---------------------------------------------------------------------

class TimelineModel:
    def __init__(self):
        self.frames = []
        self.file_paths = []
        self.durations_ms = []
        self._total_duration = 0

    def load(self, paths, anchor='bottom'):
        imgs = load_and_pad_images(paths, anchor)
        self.frames = imgs
        self.file_paths = paths
        self.durations_ms = [DEFAULT_DURATION_MS] * len(imgs)
        self._calc_total()

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
# GUI
# ---------------------------------------------------------------------

class SpriteStudioApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Sprite Animation Studio")
        self.root.geometry("920x720")
        self.root.minsize(800, 600)
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

        # Autocomplete
        self.autocomplete_list = []
        self.autocomplete_popup = None
        self.autocomplete_listbox = None
        self.autocomplete_selected_index = -1

        self._build_ui()
        self._update_autocomplete_list()

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
        # Contenitore principale con scrollbar
        main_canvas = tk.Canvas(self.root, bg='white', highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.root, orient='vertical', command=main_canvas.yview)
        scrollable_frame = ttk.Frame(main_canvas)

        scrollable_frame.bind(
            '<Configure>',
            lambda e: main_canvas.configure(scrollregion=main_canvas.bbox('all'))
        )
        def _on_canvas_configure(event):
            main_canvas.itemconfig(window_id, width=event.width)
        window_id = main_canvas.create_window((0,0), window=scrollable_frame, anchor='nw')
        main_canvas.bind('<Configure>', _on_canvas_configure)

        main_canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        parent = scrollable_frame
        parent.configure(style='TFrame')
        style = ttk.Style()
        style.theme_use('clam')

        # ----- 1. Sorgente -----
        src_frame = ttk.LabelFrame(parent, text="1. Fonte sprite")
        src_frame.pack(fill='x', padx=10, pady=5)

        rb_code = ttk.Radiobutton(src_frame, text="Codice (cerca in cartella)", variable=self.mode, value="code", command=self._on_mode_change)
        rb_folder = ttk.Radiobutton(src_frame, text="Cartella (unisci tutti)", variable=self.mode, value="folder", command=self._on_mode_change)
        rb_manual = ttk.Radiobutton(src_frame, text="Selezione manuale", variable=self.mode, value="manual", command=self._on_mode_change)

        rb_code.grid(row=0, column=0, sticky='w', padx=5, pady=2)
        rb_folder.grid(row=1, column=0, sticky='w', padx=5, pady=2)
        rb_manual.grid(row=2, column=0, sticky='w', padx=5, pady=2)

        # Code mode
        self.code_frame = ttk.Frame(src_frame)
        ttk.Label(self.code_frame, text="Codice:").pack(side='left')
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

        # Folder mode
        self.folder_frame = ttk.Frame(src_frame)
        ttk.Button(self.folder_frame, text="Scegli cartella...", command=self._pick_merge_folder).pack(side='left')
        self.folder_lbl = ttk.Label(self.folder_frame, text="(nessuna)", foreground='#666')
        self.folder_lbl.pack(side='left', padx=5)
        self.folder_filter_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.folder_frame, text="Filtra per codice", variable=self.folder_filter_var, command=self._on_mode_change).pack(side='left', padx=5)
        self.folder_code_entry = ttk.Entry(self.folder_frame, textvariable=self.code_var, width=8)
        self.folder_code_entry.pack(side='left')

        # Manual mode
        self.manual_frame = ttk.Frame(src_frame)
        ttk.Button(self.manual_frame, text="Aggiungi immagini...", command=self._add_manual_files).pack(side='left')
        ttk.Button(self.manual_frame, text="Svuota", command=self._clear_manual).pack(side='left', padx=5)
        self.manual_count_lbl = ttk.Label(self.manual_frame, text="0 file", foreground='#666')
        self.manual_count_lbl.pack(side='left', padx=5)

        self.code_frame.grid(row=0, column=1, sticky='w', padx=5, pady=3)
        self.folder_frame.grid(row=1, column=1, sticky='w', padx=5, pady=3)
        self.manual_frame.grid(row=2, column=1, sticky='w', padx=5, pady=3)
        src_frame.columnconfigure(1, weight=1)

        # Drag & drop
        dnd_text = "Trascina qui immagini" if DND_AVAILABLE else "Drag & drop non disponibile"
        self.dnd_area = tk.Label(parent, text=dnd_text, bg='#fafafa', relief='ridge', height=2, font=('Segoe UI',9,'italic'))
        self.dnd_area.pack(fill='x', padx=10, pady=5)
        if DND_AVAILABLE:
            self.dnd_area.drop_target_register(DND_FILES)
            self.dnd_area.dnd_bind('<<Drop>>', self._on_drop)

        # Load button
        load_frame = ttk.Frame(parent)
        load_frame.pack(fill='x', padx=10, pady=5)
        ttk.Button(load_frame, text="Carica frame", command=self.load_frames).pack(side='left')
        self.status_lbl = ttk.Label(load_frame, text="Nessun frame caricato", foreground='#666')
        self.status_lbl.pack(side='left', padx=15)

        # ----- 2. Timeline -----
        timeline_frame = ttk.LabelFrame(parent, text="2. Timeline e anteprima")
        timeline_frame.pack(fill='both', expand=True, padx=10, pady=5)

        self.canvas = tk.Canvas(timeline_frame, bg='#eee', height=160, highlightthickness=0)
        self.canvas.pack(fill='both', expand=True, padx=5, pady=5)

        # Player controls
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

        # Timeline thumbnails
        timeline_toolbar = ttk.Frame(timeline_frame)
        timeline_toolbar.pack(fill='x', padx=5, pady=3)
        ttk.Label(timeline_toolbar, text="Frame:").pack(side='left')
        self.frame_count_lbl = ttk.Label(timeline_toolbar, text="0", foreground='#666')
        self.frame_count_lbl.pack(side='left', padx=5)

        thumb_canvas = tk.Canvas(timeline_frame, bg='#f0f0f0', height=70, highlightthickness=0)
        thumb_canvas.pack(fill='x', padx=5, pady=5)
        self.thumb_canvas = thumb_canvas
        self.thumb_refs = []

        # ----- 3. Esportazione -----
        export_frame = ttk.LabelFrame(parent, text="3. Esporta animazione")
        export_frame.pack(fill='x', padx=10, pady=5)

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

    # -------------------- Autocomplete interattivo --------------------

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
        # Aggiorna i suggerimenti
        self._show_suggestions()

    def _show_suggestions(self):
        """Crea o aggiorna il popup dei suggerimenti."""
        prefix = self.code_var.get().upper()
        matches = [p for p in self.autocomplete_list if p.startswith(prefix)] if prefix else []

        # Chiudi il popup se non ci sono corrispondenze
        if not matches:
            self._close_autocomplete()
            return

        # Se il popup esiste già, aggiorna la lista
        if self.autocomplete_popup and self.autocomplete_popup.winfo_exists():
            self.autocomplete_listbox.delete(0, tk.END)
            for m in matches:
                self.autocomplete_listbox.insert(tk.END, m)
            self.autocomplete_selected_index = -1
            # Riposiziona sotto la entry
            self._position_popup()
            return

        # Crea nuovo popup
        popup = tk.Toplevel(self.root)
        popup.wm_overrideredirect(True)
        popup.configure(bg='white', relief='solid', bd=1)
        popup.takefocus = False  # non ruba il focus

        listbox = tk.Listbox(popup, height=min(6, len(matches)), font=('Segoe UI', 10), selectmode='single', takefocus=False)
        listbox.pack(fill='both', expand=True)
        for m in matches:
            listbox.insert(tk.END, m)

        self.autocomplete_popup = popup
        self.autocomplete_listbox = listbox
        self.autocomplete_selected_index = -1

        # Posiziona il popup
        self._position_popup()

        # Binding per selezione con mouse
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
            # Seleziona il prossimo elemento
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
        # Se c'è un popup e un elemento selezionato, seleziona e chiudi
        if self.autocomplete_popup and self.autocomplete_popup.winfo_exists():
            if self.autocomplete_selected_index >= 0:
                self._select_autocomplete()
                # Dopo selezione, il popup si chiude; il focus rimane sulla entry
                # e possiamo premere di nuovo Invio per caricare
                return "break"
        # Se non c'è popup o nessuna selezione, manda il focus al pulsante Carica?
        # Invece di spostare il focus, lasciamo che l'utente prema Invio per attivare il caricamento
        # Quindi qui possiamo invocare load_frames() direttamente
        self.load_frames()
        return "break"

    def _on_tab(self, event):
        # Se c'è popup, seleziona l'elemento corrente (o il primo) e chiudi
        if self.autocomplete_popup and self.autocomplete_popup.winfo_exists():
            if self.autocomplete_selected_index < 0:
                # seleziona il primo
                self.autocomplete_selected_index = 0
                self.autocomplete_listbox.selection_clear(0, tk.END)
                self.autocomplete_listbox.selection_set(0)
            self._select_autocomplete()
            return "break"

    def _on_listbox_click(self, event):
        # Click su un elemento del listbox lo seleziona e chiude il popup
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

    def _on_drop(self, event):
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

    # -------------------- Caricamento frame --------------------

    def _gather_paths(self):
        m = self.mode.get()
        code = self.code_var.get().strip()
        if m == 'code':
            if not self.folder_var.get():
                messagebox.showwarning("Attenzione", "Scegli una cartella.")
                return []
            if not is_valid_code(code):
                messagebox.showwarning("Attenzione", "Codice non valido (1-6 alfanumerici).")
                return []
            pattern = build_pattern(code)
            folder = Path(self.folder_var.get())
            files = [f for f in folder.iterdir() if f.is_file() and pattern.match(f.name)]
            return sort_sprite_files(files, code)
        elif m == 'folder':
            if not self.folder_var.get():
                messagebox.showwarning("Attenzione", "Scegli una cartella.")
                return []
            folder = Path(self.folder_var.get())
            if self.folder_filter_var.get():
                if not is_valid_code(code):
                    messagebox.showwarning("Attenzione", "Codice non valido per filtro.")
                    return []
                pattern = build_pattern(code)
                files = [f for f in folder.iterdir() if f.is_file() and pattern.match(f.name)]
                return sort_sprite_files(files, code)
            else:
                files = [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in IMG_EXTENSIONS]
                return sort_sprite_files(files, '')
        else:  # manual
            if not self.manual_files:
                messagebox.showwarning("Attenzione", "Nessuna immagine selezionata.")
                return []
            if code:
                pattern = build_pattern(code)
                files = [f for f in self.manual_files if pattern.match(f.name)]
            else:
                files = self.manual_files
            return sort_sprite_files(files, code)

    def load_frames(self):
        self._stop()
        paths = self._gather_paths()
        if not paths:
            self.status_lbl.config(text="Nessun file trovato")
            self.timeline.clear()
            self._update_display()
            return

        anchor = self.anchor_var.get()
        self.timeline.load(paths, anchor)
        if not self.timeline.frames:
            self.status_lbl.config(text="Errore nel caricamento")
            return

        self.current_frame_idx = 0
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

    def _draw_thumbnails(self):
        self.thumb_canvas.delete('all')
        self.thumb_refs.clear()
        if not self.timeline.frames:
            return
        thumb_w = 50
        thumb_h = 50
        spacing = 6
        total_w = len(self.timeline.frames) * (thumb_w + spacing)
        self.thumb_canvas.config(scrollregion=(0,0,total_w,thumb_h+20))

        for i, img in enumerate(self.timeline.frames):
            thumb = img.copy()
            thumb.thumbnail((thumb_w, thumb_h), Image.NEAREST)
            tk_thumb = ImageTk.PhotoImage(thumb)
            self.thumb_refs.append(tk_thumb)
            x = i * (thumb_w + spacing)
            y = 5
            self.thumb_canvas.create_rectangle(x, y, x+thumb_w, y+thumb_h, outline='#aaa', fill='', width=1)
            self.thumb_canvas.create_image(x, y, anchor='nw', image=tk_thumb)
            dur = self.timeline.durations_ms[i] if i < len(self.timeline.durations_ms) else 0
            rect_id = self.thumb_canvas.create_rectangle(x, y, x+thumb_w, y+thumb_h, outline='', fill='', tags=(f'thumb_{i}',))
            self.thumb_canvas.tag_bind(f'thumb_{i}', '<Button-1>', lambda e, idx=i: self._on_thumb_click(idx))
            self.thumb_canvas.create_text(x+thumb_w//2, y+thumb_h+2, text=f"{dur}ms", font=('Segoe UI',7), anchor='n')

    def _on_thumb_click(self, idx):
        current_dur = self.timeline.durations_ms[idx] if idx < len(self.timeline.durations_ms) else DEFAULT_DURATION_MS
        new_dur = simpledialog.askinteger(
            "Durata frame",
            f"Inserisci durata in ms per il frame {idx+1}:",
            initialvalue=current_dur,
            minvalue=1,
            maxvalue=10000
        )
        if new_dur is not None:
            self.timeline.set_duration(idx, new_dur)
            self._update_display()
            self._draw_thumbnails()

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