# sprite_animation_studio/ui_export.py
"""Editor di esportazione animazioni (G14.4).

A sinistra la libreria corrente (checkbox), la durata X, l'intervallo
angoli, formato, loop e file di uscita; a destra l'anteprima in loop di
ciò che verrà esportato; sotto la timeline a blocchi a tutta larghezza.

Ogni blocco è una coppia (animazione, angolo). Come in G14.2 l'export
unisce due timeline indipendenti con l'algoritmo confini + bisect: la
sequenza dei blocchi (la "rotazione", ciclica su X) e l'animazione che
scorre dentro ciascun blocco. Con tutti i blocchi bloccati e X pari a un
giro esatto il risultato coincide con quello di G14.2.

Il dialog legge soltanto i dati ricevuti: non modifica né salva il
progetto. Lucchetti, loop e ordine dei blocchi vivono solo nel dialog.
"""
import bisect
import os
import subprocess
import sys
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from PIL import Image, ImageTk

from .constants import TICK_MS
from .models import AngleData, FrameGroup
from .sprite_utils import load_and_pad_images, export_animation
from .logger import log

# Estensioni accettate per formato: la prima è quella di default.
# Pillow sceglie il formato di scrittura dall'estensione, quindi deve
# essere coerente con il formato selezionato.
FORMAT_EXTENSIONS = {"APNG": (".apng", ".png"), "GIF": (".gif",)}

# Palette dark minimal del progetto
BG = '#2b2b2b'
CARD = '#1e1e1e'
ACCENT = '#4a9eff'
TEXT = '#ffffff'
TEXT_DIM = '#888888'
LABEL = '#cccccc'
BUTTON = '#555555'
BORDER = '#444444'
OK_COLOR = '#7ac47a'
WARN_COLOR = '#e0b96c'
ERROR_COLOR = '#e06c6c'
CUT_COLOR = '#e05555'
WARN_BG = '#3a3322'
ERROR_BG = '#3a2424'

# Colori dei blocchi della timeline
TRACK_FILL = '#262626'
BLOCK_LOCKED = '#34404f'
BLOCK_UNLOCKED = '#2c4a70'
BLOCK_GHOST = '#262b31'
BLOCK_CUT = '#242424'
LOCK_COLOR = '#9a9a9a'

MAX_X_MS = 60000        # tetto alla durata X (60 s)
PREVIEW_SIZE = 240      # lato del riquadro anteprima (px)
PLAY_INTERVAL_MS = 30   # passo del timer dell'anteprima

# Geometria della timeline (px). Dall'alto: righello, fascia lucchetti,
# blocchi, fascia toggle loop.
TL_PAD_X = 12
TL_RULER_H = 16
TL_BLOCK_TOP = 34
TL_BLOCK_BOT = 78
TL_HEIGHT = 96
TL_GRIP = 6             # larghezza della zona di resize ai lati del blocco
TL_DRAG_THRESHOLD = 4   # px prima che un clic diventi un trascinamento
TL_MAGNET_PX = 6        # raggio di aggancio durante il resize

TL_CURSORS = {
    'lock': 'hand2',
    'loop': 'hand2',
    'ruler': 'hand2',
    'grip_l': 'sb_h_double_arrow',
    'grip_r': 'sb_h_double_arrow',
    'playhead': 'sb_h_double_arrow',
    'block': 'fleur',
}


def _open_folder_in_explorer(path: str) -> None:
    """Apre la cartella nel file manager di sistema (stessa logica di
    ui_welcome.py, replicata qui per non creare dipendenze cross-modulo)."""
    try:
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.run(["open", path])
        else:
            subprocess.run(["xdg-open", path])
    except Exception as e:
        # Tkinter inghiottirebbe l'eccezione nel callback: la logghiamo noi
        log.error(f"Impossibile aprire la cartella {path}: {e}", exc_info=True)


def _format_seconds(ms):
    """Millisecondi -> secondi senza zeri inutili (3300 -> '3.3',
    448 -> '0.448'). Tre decimali bastano: le durate sono ms interi."""
    return f"{ms / 1000:.3f}".rstrip('0').rstrip('.')


def _parse_seconds(text):
    """Secondi scritti dall'utente (accetta anche la virgola) -> ms
    interi. None se il valore non è valido o è fuori da (0, MAX_X_MS]."""
    try:
        ms = round(float(text.strip().replace(',', '.')) * 1000)
    except (ValueError, OverflowError):
        return None
    if ms <= 0 or ms > MAX_X_MS:
        return None
    return ms


def _nearest_angle(frame_group, target_angle):
    """AngleData disponibile più vicino all'angolo richiesto; a parità di
    distanza vince il più basso (stessa regola di G14.2). None se il
    frame non ha alcun angolo."""
    available = sorted(a.angle for a in frame_group.angles)
    if not available:
        return None
    chosen = available[0]
    best_dist = abs(chosen - target_angle)
    for a in available[1:]:
        d = abs(a - target_angle)
        if d < best_dist:
            chosen = a
            best_dist = d
    return frame_group.get_angle(chosen)


def _resolve_frames(frames, project_root):
    """Copia dei FrameGroup con percorsi assoluti (stessa regola di
    TimelineModel.load_from_animation). I dati del progetto non vengono
    toccati."""
    resolved = []
    for frame_group in frames:
        group = FrameGroup(letter=frame_group.letter, duration_ms=frame_group.duration_ms)
        for angle_data in frame_group.angles:
            file = angle_data.file
            if file and project_root is not None and not Path(file).is_absolute():
                file = str(Path(project_root) / file)
            group.angles.append(AngleData(angle=angle_data.angle, file=file,
                                          duration_ms=angle_data.duration_ms,
                                          mirrored=angle_data.mirrored))
        resolved.append(group)
    return resolved


class _AnimEntry:
    """Un'animazione della libreria vista dal dialog: frame con percorsi
    assoluti e confini cumulativi di un giro (l'ultimo è la D_natural)."""

    def __init__(self, key, name, code, stem, frames):
        self.key = key
        self.name = name
        self.code = code
        self.stem = stem  # nome base proposto per il file di uscita
        self.frames = frames
        self.cum = [0]
        for frame_group in frames:
            self.cum.append(self.cum[-1] + max(0, frame_group.duration_ms))
        self.d_natural = self.cum[-1]


class _Block:
    """Blocco della timeline: un'animazione mostrata a un angolo.

    Lucchetto chiuso: dura la sua D_natural. Lucchetto aperto: dura
    custom_ms, impostata trascinando i lati. Loop ON: l'animazione cicla
    dentro il blocco; loop OFF: un solo giro, poi resta sull'ultimo frame.
    """

    def __init__(self, entry, angle):
        self.entry = entry
        self.angle = angle
        self.locked = True
        self.loop = True
        self.custom_ms = None

    @property
    def key(self):
        return (self.entry.key, self.angle)

    @property
    def duration_ms(self):
        if self.locked or self.custom_ms is None:
            return self.entry.d_natural
        return self.custom_ms

    def local_boundaries(self):
        """Confini dei frame in tempo locale [0, durata]. Lucchetto chiuso:
        srotolati se il blocco cicla, un solo giro altrimenti. Lucchetto
        aperto: confini naturali scalati per riempire la durata custom."""
        duration = self.duration_ms
        natural = self.entry.d_natural
        points = {0, duration}
        if natural <= 0:
            return points
        if not self.locked:
            factor = duration / natural
            for p in self.entry.cum[1:-1]:
                points.add(p * factor)
            return points
        base = 0
        while base < duration:
            for c in self.entry.cum:
                if base + c < duration:
                    points.add(base + c)
            if not self.loop:
                break
            base += natural
        return points

    def frame_at(self, local_ms):
        """FrameGroup mostrato all'istante locale. Lucchetto chiuso:
        ciclico con loop ON, fermo sull'ultimo frame dopo il primo giro
        con loop OFF. Lucchetto aperto: scaling proporzionale delle durate
        per riempire esattamente la durata del blocco (loop ignorato)."""
        natural = self.entry.d_natural
        if natural <= 0:
            return None
        if self.locked:
            t = local_ms % natural if self.loop else min(local_ms, natural - 1)
        else:
            factor = self.duration_ms / natural
            t = local_ms / factor if factor > 0 else 0
        idx = bisect.bisect_right(self.entry.cum, t) - 1
        idx = min(max(idx, 0), len(self.entry.frames) - 1)
        return self.entry.frames[idx]


def _build_plan(blocks, x_ms):
    """Unisce le due timeline indipendenti su [0, X).

    Timeline 1: la sequenza dei blocchi, ciclica (un giro = somma delle
    durate dei blocchi). Timeline 2: l'animazione dentro ciascun blocco.
    Come in G14.2 si raccolgono tutti i confini delle due timeline e per
    ogni intervallo si cercano blocco e frame con bisect.

    Ritorna [(t0, t1, angle_data)]; angle_data è None se il frame non ha
    alcun angolo (intervallo da saltare nell'export)."""
    total = sum(b.duration_ms for b in blocks)
    if total <= 0 or x_ms <= 0:
        return []

    seq_cum = [0]
    for block in blocks:
        seq_cum.append(seq_cum[-1] + block.duration_ms)

    boundaries = {0, x_ms}
    local_points = [block.local_boundaries() for block in blocks]
    base = 0
    while base < x_ms:
        for i, points in enumerate(local_points):
            start = base + seq_cum[i]
            if start >= x_ms:
                break
            for p in points:
                if start + p <= x_ms:
                    boundaries.add(start + p)
        base += total
    boundaries = sorted(boundaries)

    segments = []
    for t0, t1 in zip(boundaries[:-1], boundaries[1:]):
        if t1 <= t0:
            continue
        cycle_t = t0 % total
        block_idx = bisect.bisect_right(seq_cum, cycle_t) - 1
        block_idx = min(max(block_idx, 0), len(blocks) - 1)
        block = blocks[block_idx]
        frame_group = block.frame_at(cycle_t - seq_cum[block_idx])
        angle_data = _nearest_angle(frame_group, block.angle) if frame_group is not None else None
        segments.append((t0, t1, angle_data))
    return segments


class ToolTip:
    """Tooltip minimale al passaggio del mouse (stessa logica di quella
    in ui_main.py, replicata per non creare dipendenze cross-modulo).
    'text' può essere una funzione: viene letta al momento di mostrarlo."""

    def __init__(self, widget, text, delay=400):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.tip = None
        self._id = None

        widget.bind('<Enter>', self._schedule, add='+')
        widget.bind('<Leave>', self._hide, add='+')
        widget.bind('<ButtonPress>', self._hide, add='+')

    def _schedule(self, event=None):
        self._cancel()
        self._id = self.widget.after(self.delay, self._show)

    def _cancel(self):
        if self._id:
            try:
                self.widget.after_cancel(self._id)
            except Exception:
                pass
            self._id = None

    def _show(self):
        text = self.text() if callable(self.text) else self.text
        if self.tip or not text:
            return
        self.tip = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.configure(bg='#333333')
        tk.Label(tw, text=text, justify='left',
                 bg='#333333', fg=TEXT,
                 font=('Segoe UI', 9),
                 padx=6, pady=3).pack()
        tw.update_idletasks()
        x = self.widget.winfo_rootx()
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        tw.wm_geometry(f"+{x}+{y}")

    def _hide(self, event=None):
        self._cancel()
        if self.tip:
            self.tip.destroy()
            self.tip = None


class ExportAnimationDialog:
    """Editor di esportazione APNG/GIF: una o più animazioni della
    libreria corrente, disposte su una timeline a blocchi lunga X."""

    def __init__(self, parent, frames, current_angle, default_path, settings, project=None,
                 target_profile_code=None):
        self.parent = parent
        self.frames = frames
        self.settings = settings
        self.project = project
        # Libreria padre scelta esplicitamente (albero di ui_main): se
        # presente, _load_library cerca il profilo per codice invece che
        # per stem di default_path e nessuna animazione risulta "corrente"
        self._target_profile_code = target_profile_code
        # default_path = root_progetto/<libreria>_<animazione>.png: la
        # cartella è il fallback di "Scegli file…", lo stem identifica
        # l'animazione caricata in timeline
        self._project_root = Path(default_path).parent
        self._name_stem = Path(default_path).stem
        # Percorso scelto con asksaveasfilename: la conferma di
        # sovrascrittura è già gestita dal dialog di sistema
        self.output_path = None

        # Libreria e blocchi
        self._entries = []
        self._check_vars = {}
        self._current_key = None
        self._profile_code = None
        self.blocks = []
        self._manual_order = False

        # Stato calcolato da _refresh
        self._x_ms = None
        self._total_ms = 0
        self._segments = []
        self._segment_starts = []

        # Anteprima e testina
        self._play_ms = 0.0
        self._playing = True
        self._last_tick = None
        self._after_id = None
        self._shown_key = False  # False = ridisegno forzato
        self._preview_photo = None  # riferimento vivo, altrimenti Tk lo raccoglie
        self._photo_cache = {}
        self._size_cache = {}
        self._pad_size = None

        # Interazione con la timeline
        self._drag = None
        self._block_spans = []
        self._ppm = 1.0  # pixel per ms della vista corrente
        self._playhead_items = ()
        self._playhead_x = None

        self.format_var = tk.StringVar(value="APNG")
        self.angle_from_var = tk.StringVar(value=str(current_angle))
        self.angle_to_var = tk.StringVar(value=str(current_angle))
        self.loop_var = tk.BooleanVar(value=True)
        self.x_var = tk.StringVar(value="")
        self.suggest_var = tk.StringVar(value="")
        self.path_label_var = tk.StringVar(value="Nessun file selezionato")
        self.open_after_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="")
        self.alert_var = tk.StringVar(value="")

        self._load_library()

        self.window = tk.Toplevel(parent)
        self.window.title("Esporta animazione")
        self.window.configure(bg=BG)
        self.window.transient(parent)
        self.window.minsize(760, 600)
        self.window.protocol("WM_DELETE_WINDOW", self._close)
        self.window.bind('<Escape>', lambda e: self._close())

        self._build_ui()

        # X iniziale: un ciclo esatto della selezione iniziale; se invece
        # non c'è alcuna animazione preselezionata (apertura da libreria
        # padre) si parte dalla durata naturale minore della libreria
        self._rebuild_blocks()
        if self.blocks:
            total = sum(b.duration_ms for b in self.blocks)
            self.x_var.set(_format_seconds(total))
        else:
            naturali = [e.d_natural for e in self._entries if e.d_natural > 0]
            self.x_var.set(_format_seconds(min(naturali)) if naturali else "")
        self.x_var.trace_add('write', lambda *_: self._refresh())
        self._refresh()

        # Centra sulla finestra principale
        self.window.update_idletasks()
        w = max(self.window.winfo_reqwidth(), 900)
        h = self.window.winfo_reqheight()
        x = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.window.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")

        self.window.grab_set()
        self.window.focus_force()

        self._last_tick = time.perf_counter()
        self._after_id = self.window.after(PLAY_INTERVAL_MS, self._tick)

    # ------------------------------------------------------------------
    # Libreria
    # ------------------------------------------------------------------

    def _load_library(self):
        """Animazioni della libreria corrente. Con target_profile_code
        (libreria padre scelta esplicitamente nell'albero di ui_main) il
        profilo si cerca per codice e nessuna animazione risulta
        "corrente". Altrimenti si riconosce libreria/animazione dallo
        stem di default_path (<libreria>_<animazione>), come finora. Per
        l'animazione corrente si usano i frame ricevuti; senza progetto o
        senza corrispondenza resta solo l'animazione corrente."""
        profile = None
        p_idx = None

        if self._target_profile_code is not None:
            if self.project is not None:
                for idx, prof in enumerate(self.project.profiles):
                    if prof.code == self._target_profile_code:
                        profile, p_idx = prof, idx
                        break
            self._current_key = None
        elif self.project is not None:
            for idx, prof in enumerate(self.project.profiles):
                for a_idx, anim in enumerate(prof.animations):
                    if f"{prof.code}_{anim.code}" == self._name_stem:
                        profile, p_idx = prof, idx
                        self._current_key = (idx, a_idx)
                        break
                if profile is not None:
                    break

        if profile is None:
            self._current_key = ('current',)
            code = self._name_stem.rsplit('_', 1)[-1]
            self._entries = [_AnimEntry(self._current_key, self._name_stem, code,
                                        self._name_stem, self.frames)]
            return

        self._profile_code = profile.code
        for a_idx, anim in enumerate(profile.animations):
            key = (p_idx, a_idx)
            if key == self._current_key:
                frames = self.frames
            else:
                frames = _resolve_frames(anim.frames, self.project.root_path)
            self._entries.append(_AnimEntry(key, anim.name, anim.code,
                                            f"{profile.code}_{anim.code}", frames))

    def _selected_entries(self):
        return [e for e in self._entries if self._check_vars[e.key].get()]

    def _selected_angles(self):
        """Angoli Da..A; lista vuota se Da > A."""
        angle_from = int(self.angle_from_var.get())
        angle_to = int(self.angle_to_var.get())
        return list(range(angle_from, angle_to + 1))

    def _rebuild_blocks(self):
        """Blocchi = animazioni spuntate x angoli Da..A (ordine: per
        animazione, poi per angolo). I blocchi già presenti conservano
        lucchetto, loop e durata; dopo un riordino manuale si conserva
        l'ordine dell'utente e i blocchi nuovi vanno in coda."""
        angles = self._selected_angles()
        existing = {b.key: b for b in self.blocks}
        fresh = []
        for entry in self._selected_entries():
            if entry.d_natural <= 0:
                continue
            for angle in angles:
                fresh.append(existing.get((entry.key, angle)) or _Block(entry, angle))

        if self._manual_order:
            order = {b.key: i for i, b in enumerate(self.blocks)}
            kept = sorted((b for b in fresh if b.key in order), key=lambda b: order[b.key])
            self.blocks = kept + [b for b in fresh if b.key not in order]
        else:
            self.blocks = fresh
        if not self.blocks:
            self._manual_order = False

    # ------------------------------------------------------------------
    # Costruzione UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        label_opts = dict(font=('Segoe UI', 10), bg=CARD, fg=LABEL)
        toggle_opts = dict(font=('Segoe UI', 10), bg=CARD, fg=TEXT,
                           selectcolor=CARD, activebackground=CARD,
                           activeforeground=TEXT)

        # Riga 1: campi a sinistra, anteprima a destra, metà ciascuno
        top = tk.Frame(self.window, bg=BG)
        top.pack(fill='both', expand=True, padx=16, pady=(16, 8))
        top.columnconfigure(0, weight=1, uniform='half')
        top.columnconfigure(1, weight=1, uniform='half')
        top.rowconfigure(0, weight=1)

        left = tk.Frame(top, bg=CARD, padx=14, pady=12)
        left.grid(row=0, column=0, sticky='nsew', padx=(0, 8))
        right = tk.Frame(top, bg=CARD, padx=14, pady=12)
        right.grid(row=0, column=1, sticky='nsew', padx=(8, 0))

        self._build_fields(left, label_opts, toggle_opts)

        preview_header = tk.Frame(right, bg=CARD)
        preview_header.pack(fill='x')
        tk.Label(preview_header, text="Anteprima", **label_opts).pack(side='left')

        self.preview_canvas = tk.Canvas(right, width=PREVIEW_SIZE, height=PREVIEW_SIZE,
                                        bg=CARD, highlightthickness=1,
                                        highlightbackground=BORDER)
        self.preview_canvas.pack(expand=True)

        # Pulsanti pausa/riavvia sotto l'anteprima, centrati
        preview_controls = tk.Frame(right, bg=CARD)
        preview_controls.pack()
        self.play_pause_var = tk.StringVar(value="⏸")
        self.play_pause_btn = tk.Button(preview_controls, textvariable=self.play_pause_var,
                                        font=('Segoe UI', 14), bg=BUTTON, fg=TEXT,
                                        relief='flat', width=3, padx=10, takefocus=0,
                                        command=self._toggle_playing)
        self.play_pause_btn.pack(side='left', padx=(0, 6))
        self.restart_btn = tk.Button(preview_controls, text="⟲", font=('Segoe UI', 14),
                                     bg=BUTTON, fg=TEXT, relief='flat', width=3, padx=10, takefocus=0,
                                     command=self._restart_preview)
        self.restart_btn.pack(side='left')
        ToolTip(self.restart_btn, "Riavvia anteprima")

        # Riga 2: timeline a tutta larghezza, barra alert e pulsanti
        bottom = tk.Frame(self.window, bg=BG)
        bottom.pack(fill='x', padx=16, pady=(0, 14))

        self.timeline = tk.Canvas(bottom, height=TL_HEIGHT, bg=CARD, highlightthickness=0)
        self.timeline.pack(fill='x')
        self.timeline.bind('<Configure>', lambda e: self._draw_timeline())
        self.timeline.bind('<Motion>', self._on_tl_motion)
        self.timeline.bind('<ButtonPress-1>', self._on_tl_press)
        self.timeline.bind('<B1-Motion>', self._on_tl_drag)
        self.timeline.bind('<ButtonRelease-1>', self._on_tl_release)

        actions = tk.Frame(bottom, bg=BG)
        actions.pack(fill='x', pady=(8, 0))
        actions.columnconfigure(0, weight=1)

        # Esito dell'ultimo export (a sinistra) e alert sottile sopra Esporta
        self.status_label = tk.Label(actions, textvariable=self.status_var,
                                     font=('Segoe UI', 9), bg=BG, fg=OK_COLOR, anchor='w')
        self.status_label.grid(row=0, column=0, sticky='ew')
        self.alert_label = tk.Label(actions, textvariable=self.alert_var,
                                    font=('Segoe UI', 8, 'bold'), bg=BG, fg=WARN_COLOR)
        self.alert_label.grid(row=0, column=1, sticky='ew', padx=(0, 8), pady=(0, 3))
        ToolTip(self.alert_label, self._cycles_tooltip)

        tk.Checkbutton(actions, text="Apri cartella dopo export", variable=self.open_after_var,
                       font=('Segoe UI', 10), bg=BG, fg=TEXT, selectcolor=BG,
                       activebackground=BG, activeforeground=TEXT
                       ).grid(row=1, column=0, sticky='w')
        tk.Button(actions, text="Esporta", font=('Segoe UI', 10, 'bold'),
                  bg=ACCENT, fg='white', relief='flat', padx=18, pady=6,
                  command=self._on_export).grid(row=1, column=1, sticky='ew', padx=(0, 8))
        tk.Button(actions, text="Annulla", font=('Segoe UI', 10),
                  bg=BUTTON, fg='white', relief='flat', padx=18, pady=6,
                  command=self._close).grid(row=1, column=2, sticky='ew')

    def _build_fields(self, parent, label_opts, toggle_opts):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        tk.Label(parent, text="Cosa esportare", **label_opts).grid(row=0, column=0, sticky='w')
        self._build_library_list(parent).grid(row=1, column=0, sticky='nsew', pady=(4, 10))

        # Durata X: sopra il campo, piccolo, il valore suggerito
        x_row = tk.Frame(parent, bg=CARD)
        x_row.grid(row=2, column=0, sticky='w', pady=(0, 6))
        tk.Label(x_row, text="Durata X (s):", **label_opts).grid(row=1, column=0, sticky='w',
                                                                 padx=(0, 8))
        self.suggest_label = tk.Label(x_row, textvariable=self.suggest_var,
                                      font=('Segoe UI', 8), bg=CARD, fg=ACCENT, anchor='w',
                                      cursor='hand2')
        self.suggest_label.grid(row=0, column=1, sticky='w')
        self.suggest_label.bind('<Button-1>', self._apply_suggestion)
        ToolTip(self.suggest_label, self._cycles_tooltip)
        tk.Entry(x_row, textvariable=self.x_var, width=8, font=('Segoe UI', 10),
                 bg='#333333', fg=TEXT, insertbackground=TEXT, relief='flat'
                 ).grid(row=1, column=1, sticky='w')

        angle_row = tk.Frame(parent, bg=CARD)
        angle_row.grid(row=3, column=0, sticky='w', pady=4)
        tk.Label(angle_row, text="Da angolo:", **label_opts).pack(side='left')
        from_combo = ttk.Combobox(angle_row, textvariable=self.angle_from_var, state='readonly',
                                  values=[str(a) for a in range(1, 9)], width=3)
        from_combo.pack(side='left', padx=(6, 16))
        tk.Label(angle_row, text="A angolo:", **label_opts).pack(side='left')
        to_combo = ttk.Combobox(angle_row, textvariable=self.angle_to_var, state='readonly',
                                values=[str(a) for a in range(1, 9)], width=3)
        to_combo.pack(side='left', padx=(6, 0))
        for combo in (from_combo, to_combo):
            combo.bind('<<ComboboxSelected>>', lambda e: self._on_selection_changed())

        fmt_row = tk.Frame(parent, bg=CARD)
        fmt_row.grid(row=4, column=0, sticky='w', pady=4)
        tk.Label(fmt_row, text="Formato:", **label_opts).pack(side='left', padx=(0, 8))
        for fmt in FORMAT_EXTENSIONS:
            tk.Radiobutton(fmt_row, text=fmt, variable=self.format_var, value=fmt,
                           command=self._on_format_changed,
                           **toggle_opts).pack(side='left', padx=(0, 12))

        tk.Checkbutton(parent, text="Loop", variable=self.loop_var,
                       **toggle_opts).grid(row=5, column=0, sticky='w', pady=4)

        tk.Button(parent, text="Scegli file…", font=('Segoe UI', 9),
                  bg=BUTTON, fg='white', relief='flat', padx=10,
                  command=self._choose_file).grid(row=6, column=0, sticky='w', pady=(6, 2))
        self.path_label = tk.Label(parent, textvariable=self.path_label_var,
                                   font=('Segoe UI', 8), bg=CARD, fg=TEXT_DIM,
                                   anchor='w', justify='left', wraplength=380)
        self.path_label.grid(row=7, column=0, sticky='w')
        self.path_label.bind('<Button-1>', self._open_output_folder)

    def _build_library_list(self, parent):
        """Lista scorrevole delle animazioni della libreria: checkbox a
        sinistra, nome e codice a destra. Libreria senza animazioni: un
        messaggio al posto della lista (es. libreria padre vuota)."""
        holder = tk.Frame(parent, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        if not self._entries:
            tk.Label(holder, text="Nessuna animazione nella libreria",
                    font=('Segoe UI', 9), bg=CARD, fg=TEXT_DIM).pack(pady=8)
            return holder

        canvas = tk.Canvas(holder, bg=CARD, highlightthickness=0, height=120, width=10)
        scrollbar = ttk.Scrollbar(holder, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        inner = tk.Frame(canvas, bg=CARD)
        inner_id = canvas.create_window(0, 0, window=inner, anchor='nw')
        inner.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfigure(inner_id, width=e.width))

        def on_wheel(event):
            canvas.yview_scroll(int(-event.delta / 120), 'units')

        for widget in (canvas, inner):
            widget.bind('<MouseWheel>', on_wheel)

        for entry in self._entries:
            enabled = entry.d_natural > 0
            var = tk.BooleanVar(value=enabled and entry.key == self._current_key)
            self._check_vars[entry.key] = var

            row = tk.Frame(inner, bg=CARD)
            row.pack(fill='x')
            check = tk.Checkbutton(row, variable=var, command=self._on_selection_changed,
                                   bg=CARD, fg=TEXT, selectcolor=CARD,
                                   activebackground=CARD, activeforeground=TEXT,
                                   state='normal' if enabled else 'disabled')
            check.pack(side='left')
            name = tk.Label(row, text=entry.name if enabled else f"{entry.name} (vuota)",
                            font=('Segoe UI', 9), bg=CARD,
                            fg=TEXT if enabled else TEXT_DIM, anchor='w')
            name.pack(side='left', fill='x', expand=True)
            code = tk.Label(row, text=entry.code, font=('Consolas', 9), bg=CARD, fg=TEXT_DIM)
            code.pack(side='right', padx=(4, 6))

            for widget in (row, check, name, code):
                widget.bind('<MouseWheel>', on_wheel)
            if enabled:
                # Il clic su nome o codice spunta come il clic sulla checkbox
                for widget in (name, code):
                    widget.bind('<Button-1>', lambda e, v=var: self._toggle_entry(v))
        return holder

    # ------------------------------------------------------------------
    # Stato: selezione, X, suggerimento, alert
    # ------------------------------------------------------------------

    def _toggle_entry(self, var):
        var.set(not var.get())
        self._on_selection_changed()

    def _on_selection_changed(self):
        self._rebuild_blocks()
        self._refresh()

    def _refresh(self):
        """Ricalcola X, durata della sequenza e piano di export, poi
        aggiorna suggerimento, alert, timeline e anteprima."""
        self._x_ms = _parse_seconds(self.x_var.get())
        self._total_ms = sum(b.duration_ms for b in self.blocks)
        if self._x_ms and self._total_ms > 0:
            self._segments = _build_plan(self.blocks, self._x_ms)
        else:
            self._segments = []
        self._segment_starts = [s[0] for s in self._segments]

        sugg_ms, _ = self._suggestion()
        self.suggest_var.set(_format_seconds(sugg_ms) if sugg_ms else "")
        self._update_alert()
        self._update_pad_size()

        self._play_ms = self._play_ms % self._x_ms if self._x_ms else 0.0
        self._shown_key = False
        self._draw_timeline()
        self._show_preview_at(self._play_ms)

    def _suggestion(self):
        """(ms, cicli): il multiplo esatto della sequenza più vicino a X,
        almeno un ciclo e non oltre il tetto di X."""
        total = self._total_ms
        if total <= 0:
            return None, 0
        cycles = max(1, round((self._x_ms or total) / total))
        while cycles > 1 and cycles * total > MAX_X_MS:
            cycles -= 1
        return cycles * total, cycles

    def _apply_suggestion(self, _event=None):
        """Il clic sul valore suggerito lo applica a X (l'alert si
        aggiorna da sé: x_var ha già una trace su _refresh)."""
        sugg_ms, _ = self._suggestion()
        if sugg_ms:
            self.x_var.set(_format_seconds(sugg_ms))

    def _cycles_tooltip(self):
        total = self._total_ms
        if total <= 0:
            return ""
        _, cycles = self._suggestion()
        lines = ["chiude 1 ciclo esatto" if cycles == 1 else f"chiude {cycles} cicli esatti"]
        for n in sorted({1, 2, 3, 4, cycles - 1, cycles + 1} - {0, cycles}):
            if n * total <= MAX_X_MS:
                lines.append(f"{n} {'ciclo' if n == 1 else 'cicli'} = {_format_seconds(n * total)}s")
        return "\n".join(lines)

    def _update_alert(self):
        """Barra sottile sopra Esporta: il valore suggerito quando X non è
        un multiplo esatto della sequenza (l'export taglia), oppure un
        errore che blocca l'export."""
        text, fg, bg = "", WARN_COLOR, BG
        if not self._selected_angles():
            text, fg, bg = "Da > A", ERROR_COLOR, ERROR_BG
        elif self._total_ms <= 0:
            pass
        elif self._x_ms is None:
            text, fg, bg = "X non valido", ERROR_COLOR, ERROR_BG
        elif self._x_ms % self._total_ms:
            sugg_ms, _ = self._suggestion()
            text, bg = f"⚠ {_format_seconds(sugg_ms)}", WARN_BG
        self.alert_var.set(text)
        self.alert_label.configure(fg=fg, bg=bg)

    def _set_status(self, text, color=OK_COLOR):
        self.status_var.set(text)
        self.status_label.configure(fg=color)

    # ------------------------------------------------------------------
    # File di uscita
    # ------------------------------------------------------------------

    def _default_file_name(self, ext):
        selected = self._selected_entries()
        if len(selected) == 1:
            stem = selected[0].stem
        elif selected and self._profile_code:
            stem = f"{self._profile_code}_" + "-".join(e.code for e in selected)
        else:
            stem = self._name_stem
        angle_from = self.angle_from_var.get()
        angle_to = self.angle_to_var.get()
        if angle_from == angle_to:
            return f"{stem}_angle{angle_from}{ext}"
        return f"{stem}_rot{angle_from}-{angle_to}{ext}"

    def _choose_file(self):
        """Un unico dialog di sistema per cartella e nome del file. Parte
        dall'ultima cartella di esportazione (o dalla root del progetto)."""
        fmt = self.format_var.get()
        exts = FORMAT_EXTENSIONS[fmt]
        initialdir = self.settings.get("paths", "last_export_dir", "") or str(self._project_root)
        path = filedialog.asksaveasfilename(
            parent=self.window,
            title="Esporta animazione",
            initialdir=initialdir,
            initialfile=self._default_file_name(exts[0]),
            defaultextension=exts[0],
            filetypes=[(fmt, " ".join("*" + e for e in exts))],
        )
        if path:
            self.output_path = Path(path)
            self._update_path_label()

    def _update_path_label(self):
        if self.output_path is None:
            self.path_label_var.set("Nessun file selezionato")
            self.path_label.configure(fg=TEXT_DIM, cursor='')
        else:
            self.path_label_var.set(str(self.output_path))
            self.path_label.configure(fg=ACCENT, cursor='hand2')

    def _on_format_changed(self):
        """Pillow sceglie il formato dall'estensione: se il file scelto non
        è coerente col nuovo formato va scelto di nuovo."""
        if self.output_path is None:
            return
        if self.output_path.suffix.lower() not in FORMAT_EXTENSIONS[self.format_var.get()]:
            self.output_path = None
            self._update_path_label()

    def _open_output_folder(self, _event=None):
        if self.output_path is not None:
            _open_folder_in_explorer(str(self.output_path.parent))

    # ------------------------------------------------------------------
    # Timeline: disegno
    # ------------------------------------------------------------------

    def _time_to_x(self, ms):
        return TL_PAD_X + ms * self._ppm

    def _draw_timeline(self):
        """Righello, blocchi della sequenza, ripetizioni fino a X (cicli
        successivi, non interattive), taglio oltre X e testina."""
        c = self.timeline
        c.delete('all')
        self._block_spans = []
        self._playhead_items = ()
        self._playhead_x = None

        width = max(c.winfo_width(), 200)
        x_ms = self._x_ms or 0
        total = self._total_ms
        scale = max(x_ms, total)
        if not self.blocks or scale <= 0:
            text = "Nessuna animazione selezionata" if self._selected_angles() \
                else "Intervallo angoli non valido"
            c.create_text(width / 2, TL_HEIGHT / 2, text=text, fill=TEXT_DIM,
                          font=('Segoe UI', 9))
            return
        self._ppm = (width - 2 * TL_PAD_X) / scale

        self._draw_ruler(scale)
        if x_ms:
            c.create_rectangle(self._time_to_x(0), TL_BLOCK_TOP, self._time_to_x(x_ms),
                               TL_BLOCK_BOT, fill=TRACK_FILL, outline='')

        drag = self._drag if self._drag and self._drag.get('moved') else None
        resizing = self._drag['index'] if self._drag and self._drag['kind'] in ('grip_l', 'grip_r') \
            else None

        # Blocchi reali: il primo giro della sequenza
        start = 0
        for i, block in enumerate(self.blocks):
            end = start + block.duration_ms
            x0, x1 = self._time_to_x(start), self._time_to_x(end)
            self._block_spans.append((x0, x1))
            self._draw_block(block, x0, x1, start, end, x_ms,
                             lifted=drag is not None and drag['index'] == i,
                             resizing=resizing == i)
            start = end

        # Cicli successivi fino a X
        if x_ms > total > 0:
            t = total
            while t < x_ms:
                for block in self.blocks:
                    if t >= x_ms:
                        break
                    x0 = self._time_to_x(t)
                    x1 = self._time_to_x(min(t + block.duration_ms, x_ms))
                    c.create_rectangle(x0, TL_BLOCK_TOP, x1, TL_BLOCK_BOT,
                                       fill=BLOCK_GHOST, outline=CARD)
                    if x1 - x0 >= 18:
                        c.create_text((x0 + x1) / 2, (TL_BLOCK_TOP + TL_BLOCK_BOT) / 2,
                                      text=block.entry.code, fill='#555a62',
                                      font=('Segoe UI', 9, 'bold'))
                    t += block.duration_ms

        # X più corto della sequenza: linea rossa dove finisce X
        if 0 < x_ms < total:
            xc = self._time_to_x(x_ms)
            c.create_line(xc, TL_RULER_H, xc, TL_HEIGHT, fill=CUT_COLOR, width=2)
            c.create_text(xc + 3, TL_RULER_H + 1, text="X", anchor='nw',
                          fill=CUT_COLOR, font=('Segoe UI', 7, 'bold'))

        if drag is not None:
            self._draw_reorder_feedback(drag)

        if x_ms:
            x = self._time_to_x(self._play_ms)
            line = c.create_line(x, 0, x, TL_HEIGHT, fill=TEXT)
            head = c.create_polygon(x - 5, 0, x + 5, 0, x, 7, fill=TEXT, outline='')
            self._playhead_items = (line, head)
            self._playhead_x = x

    def _draw_ruler(self, scale):
        c = self.timeline
        step = next((s for s in (100, 250, 500, 1000, 2000, 5000, 10000)
                     if s * self._ppm >= 48), 10000)
        t = 0
        while t <= scale:
            x = self._time_to_x(t)
            c.create_line(x, TL_RULER_H - 5, x, TL_RULER_H, fill=BUTTON)
            c.create_text(x + 2, 1, text=f"{_format_seconds(t)}s", anchor='nw',
                          fill=TEXT_DIM, font=('Segoe UI', 7))
            t += step
        c.create_line(TL_PAD_X, TL_RULER_H, self._time_to_x(scale), TL_RULER_H, fill='#3a3a3a')

    def _draw_block(self, block, x0, x1, start, end, x_ms, lifted, resizing):
        c = self.timeline
        fill = BLOCK_LOCKED if block.locked else BLOCK_UNLOCKED
        c.create_rectangle(x0, TL_BLOCK_TOP, x1, TL_BLOCK_BOT,
                           fill=BLOCK_GHOST if lifted else fill, outline=CARD)

        # La parte oltre X resta visibile ma spenta: verrà tagliata
        if 0 < x_ms < end:
            xc = max(x0, self._time_to_x(x_ms))
            c.create_rectangle(xc, TL_BLOCK_TOP, x1, TL_BLOCK_BOT, fill=BLOCK_CUT, outline=CARD)
        beyond = 0 < x_ms <= (start + end) / 2

        width = x1 - x0
        cx = (x0 + x1) / 2
        cy = (TL_BLOCK_TOP + TL_BLOCK_BOT) / 2
        if width >= 18:
            c.create_text(cx, cy - 6, text=block.entry.code,
                          fill='#666666' if beyond else TEXT, font=('Segoe UI', 9, 'bold'))
            # Sotto il codice l'angolo; durante il resize la durata del blocco
            sub = f"{_format_seconds(block.duration_ms)}s" if resizing else str(block.angle)
            c.create_text(cx, cy + 9, text=sub, fill=TEXT_DIM, font=('Segoe UI', 7))

        if not block.locked:
            grips = [x1 - 3] if width <= 3 * TL_GRIP else [x0 + 3, x1 - 3]
            for gx in grips:
                c.create_line(gx, TL_BLOCK_TOP + 12, gx, TL_BLOCK_BOT - 12, fill=ACCENT, width=2)

        if width >= 12:
            self._draw_lock(cx, TL_BLOCK_TOP - 1, block.locked)
        if width >= 20:
            self._draw_loop_toggle(cx, TL_BLOCK_BOT, block.loop, enabled=block.locked)

    def _draw_lock(self, cx, bottom, locked):
        """Lucchetto appoggiato al bordo superiore del blocco: chiuso
        grigio, aperto (arco sollevato) nel colore d'accento."""
        c = self.timeline
        color = LOCK_COLOR if locked else ACCENT
        c.create_rectangle(cx - 5, bottom - 7, cx + 5, bottom, fill=color, outline=color)
        lift = 0 if locked else 3
        c.create_arc(cx - 3, bottom - 14 - lift, cx + 3, bottom - 6 - lift,
                     start=0, extent=180, style='arc', outline=color, width=2)
        c.create_line(cx + 3, bottom - 10 - lift, cx + 3, bottom - 7, fill=color, width=2)
        if locked:
            c.create_line(cx - 3, bottom - 10, cx - 3, bottom - 7, fill=color, width=2)
        else:
            c.create_line(cx - 3, bottom - 10 - lift, cx - 3, bottom - 11, fill=color, width=2)

    def _draw_loop_toggle(self, cx, top, loop, enabled=True):
        """Blocco bloccato: toggle attivo. Blocco aperto: la durata è già
        scalata, il loop non ha effetto e il toggle appare disabilitato."""
        c = self.timeline
        if not enabled:
            c.create_rectangle(cx - 9, top + 2, cx + 9, top + 15, fill=CARD, outline=BUTTON)
            c.create_text(cx, top + 8, text="↻" if loop else "→", fill='#555555',
                          font=('Segoe UI', 8))
        elif loop:
            c.create_rectangle(cx - 9, top + 2, cx + 9, top + 15, fill=ACCENT, outline=ACCENT)
            c.create_text(cx, top + 8, text="↻", fill=TEXT, font=('Segoe UI', 8))
        else:
            c.create_rectangle(cx - 9, top + 2, cx + 9, top + 15, fill=CARD, outline=BUTTON)
            c.create_text(cx, top + 8, text="→", fill=TEXT_DIM, font=('Segoe UI', 8))

    def _draw_reorder_feedback(self, drag):
        """Durante il drag&drop: segnaposto di inserimento e sagoma del
        blocco che segue il mouse."""
        c = self.timeline
        spans = self._block_spans
        target = drag['target']
        gap_x = spans[target][0] if target < len(spans) else spans[-1][1]
        c.create_line(gap_x, TL_BLOCK_TOP - 4, gap_x, TL_BLOCK_BOT + 4, fill=ACCENT, width=3)

        x0, x1 = spans[drag['index']]
        left = drag['mouse_x'] - drag['grab_dx']
        c.create_rectangle(left, TL_BLOCK_TOP + 3, left + (x1 - x0), TL_BLOCK_BOT - 3,
                           outline=ACCENT, width=2)
        c.create_text(left + (x1 - x0) / 2, (TL_BLOCK_TOP + TL_BLOCK_BOT) / 2,
                      text=self.blocks[drag['index']].entry.code, fill=ACCENT,
                      font=('Segoe UI', 9, 'bold'))

    def _update_playhead(self):
        if not self._playhead_items:
            return
        x = self._time_to_x(self._play_ms)
        line, head = self._playhead_items
        self.timeline.coords(line, x, 0, x, TL_HEIGHT)
        self.timeline.coords(head, x - 5, 0, x + 5, 0, x, 7)
        self._playhead_x = x

    # ------------------------------------------------------------------
    # Timeline: interazione
    # ------------------------------------------------------------------

    def _block_index_at(self, x):
        for i, (x0, x1) in enumerate(self._block_spans):
            if x0 <= x < x1:
                return i
        return None

    def _hit_test(self, x, y):
        """(tipo, indice blocco) dell'elemento sotto il mouse. Le zone
        cliccabili coincidono con quelle disegnate in _draw_block."""
        if y < TL_RULER_H:
            return 'ruler', None
        index = self._block_index_at(x)
        if index is not None:
            x0, x1 = self._block_spans[index]
            width = x1 - x0
            cx = (x0 + x1) / 2
            block = self.blocks[index]
            if y < TL_BLOCK_TOP:
                if width >= 12 and abs(x - cx) <= 7:
                    return 'lock', index
            elif y > TL_BLOCK_BOT:
                if width >= 20 and abs(x - cx) <= 10 and block.locked:
                    return 'loop', index
            elif not block.locked:
                if x1 - x <= TL_GRIP:
                    return 'grip_r', index
                if x - x0 <= TL_GRIP and width > 3 * TL_GRIP:
                    return 'grip_l', index
        if self._playhead_x is not None and abs(x - self._playhead_x) <= 3:
            return 'playhead', None
        if index is not None and TL_BLOCK_TOP <= y <= TL_BLOCK_BOT:
            return 'block', index
        return 'empty', None

    def _on_tl_motion(self, event):
        kind, _ = self._hit_test(event.x, event.y)
        self.timeline.configure(cursor=TL_CURSORS.get(kind, ''))

    def _on_tl_press(self, event):
        kind, index = self._hit_test(event.x, event.y)
        self._drag = None
        if kind == 'lock':
            block = self.blocks[index]
            block.locked = not block.locked
            # Lucchetto chiuso = D_natural: la durata impostata si scarta
            block.custom_ms = None
            self._refresh()
        elif kind == 'loop':
            self.blocks[index].loop = not self.blocks[index].loop
            self._refresh()
        elif kind in ('ruler', 'playhead'):
            self._playing = False
            self._drag = {'kind': 'playhead'}
            self._seek_to_x(event.x)
        elif kind in ('grip_l', 'grip_r'):
            block = self.blocks[index]
            block.custom_ms = block.duration_ms
            self._drag = {'kind': kind, 'index': index, 'x0': event.x,
                          'orig': block.duration_ms, 'ppm': self._ppm}
        elif kind == 'block':
            self._drag = {'kind': 'block', 'index': index, 'x0': event.x,
                          'grab_dx': event.x - self._block_spans[index][0],
                          'moved': False, 'target': index, 'mouse_x': event.x}

    def _on_tl_drag(self, event):
        drag = self._drag
        if drag is None:
            return
        kind = drag['kind']
        if kind == 'playhead':
            self._seek_to_x(event.x)
        elif kind in ('grip_l', 'grip_r'):
            block = self.blocks[drag['index']]
            delta = (event.x - drag['x0']) / drag['ppm']
            if kind == 'grip_l':
                # Lato sinistro: tirare verso sinistra allunga il blocco
                delta = -delta
            block.custom_ms = self._snap_duration(block, drag['orig'] + delta, drag['ppm'])
            self._refresh()
        elif kind == 'block':
            if not drag['moved'] and abs(event.x - drag['x0']) < TL_DRAG_THRESHOLD:
                return
            drag['moved'] = True
            drag['mouse_x'] = event.x
            drag['target'] = self._insertion_index(event.x)
            self._draw_timeline()

    def _on_tl_release(self, event):
        drag, self._drag = self._drag, None
        if drag is None:
            return
        kind = drag['kind']
        if kind == 'playhead':
            self._playing = True
        elif kind == 'block' and drag['moved']:
            src, dst = drag['index'], drag['target']
            # target è la posizione di inserimento nella lista originale
            if dst > src:
                dst -= 1
            if dst != src:
                self.blocks.insert(dst, self.blocks.pop(src))
                self._manual_order = True
            self._refresh()
        elif kind in ('grip_l', 'grip_r'):
            self._refresh()

    def _insertion_index(self, x):
        for i, (x0, x1) in enumerate(self._block_spans):
            if x < (x0 + x1) / 2:
                return i
        return len(self._block_spans)

    def _snap_duration(self, block, raw_ms, ppm):
        """Aggancio della durata durante il resize, in ordine: la durata
        che chiude esattamente X, un numero intero di cicli
        dell'animazione, altrimenti un multiplo di tic."""
        magnet = TL_MAGNET_PX / ppm
        if self._x_ms:
            closing = self._x_ms - (self._total_ms - block.duration_ms)
            if closing >= TICK_MS and abs(raw_ms - closing) <= magnet:
                return closing
        natural = block.entry.d_natural
        cycles = max(1, round(raw_ms / natural))
        if abs(raw_ms - cycles * natural) <= magnet:
            return cycles * natural
        snapped = round(raw_ms / TICK_MS) * TICK_MS
        return min(max(TICK_MS, snapped), MAX_X_MS)

    def _seek_to_x(self, x):
        if not self._x_ms:
            return
        ms = (x - TL_PAD_X) / self._ppm
        self._play_ms = min(max(ms, 0.0), self._x_ms - 1)
        self._update_playhead()
        self._show_preview_at(self._play_ms)

    # ------------------------------------------------------------------
    # Anteprima
    # ------------------------------------------------------------------

    def _toggle_playing(self):
        """Pulsante pausa/play accanto all'anteprima: ferma o riprende
        l'avanzamento della testina senza toccarne la posizione."""
        self._playing = not self._playing
        self.play_pause_var.set("⏸" if self._playing else "▶")

    def _restart_preview(self):
        """Pulsante ⟲: riporta la testina a 0 senza toccare play/pausa."""
        self._play_ms = 0.0
        self._update_playhead()
        self._show_preview_at(0)

    def _tick(self):
        """Avanza la testina in tempo reale e ricomincia da capo a X."""
        self._after_id = None
        try:
            now = time.perf_counter()
            if self._playing and self._x_ms and self._segments and self._last_tick is not None:
                elapsed = (now - self._last_tick) * 1000.0
                self._play_ms = (self._play_ms + elapsed) % self._x_ms
                self._update_playhead()
                self._show_preview_at(self._play_ms)
            self._last_tick = now
        except Exception as e:
            # Tkinter inghiottirebbe l'eccezione: la logghiamo e fermiamo il timer
            log.error(f"Anteprima export interrotta: {e}", exc_info=True)
            return
        self._after_id = self.window.after(PLAY_INTERVAL_MS, self._tick)

    def _image_size(self, path):
        if path not in self._size_cache:
            try:
                with Image.open(path) as img:
                    self._size_cache[path] = img.size
            except Exception as e:
                log.warning(f"Anteprima export: impossibile leggere {path}: {e}")
                self._size_cache[path] = None
        return self._size_cache[path]

    def _update_pad_size(self):
        """Dimensione comune dei frame nel file esportato, come in
        load_and_pad_images: massimo di larghezza e altezza dei file usati."""
        max_w = max_h = 0
        for path in {s[2].file for s in self._segments if s[2] is not None}:
            size = self._image_size(path)
            if size:
                max_w = max(max_w, size[0])
                max_h = max(max_h, size[1])
        pad_size = (max_w, max_h) if max_w and max_h else None
        if pad_size != self._pad_size:
            self._pad_size = pad_size
            self._photo_cache.clear()

    def _preview_photo_for(self, angle_data):
        """PhotoImage del frame come apparirà nel file (ribaltato se
        mirrored, allineato in basso al centro), scalato nel riquadro."""
        key = (angle_data.file, angle_data.mirrored)
        if key in self._photo_cache:
            return self._photo_cache[key]
        photo = None
        if self._pad_size is not None:
            try:
                with Image.open(angle_data.file) as src:
                    img = src.convert('RGBA')
                if angle_data.mirrored:
                    img = img.transpose(Image.FLIP_LEFT_RIGHT)
                pad_w, pad_h = self._pad_size
                padded = Image.new('RGBA', (pad_w, pad_h), (0, 0, 0, 0))
                padded.paste(img, ((pad_w - img.width) // 2, pad_h - img.height), img)
                scale = min((PREVIEW_SIZE - 8) / pad_w, (PREVIEW_SIZE - 8) / pad_h)
                if scale >= 1:
                    # Pixel art: ingrandimento intero, niente sfocature
                    scale = int(scale)
                    resample = Image.NEAREST
                else:
                    resample = Image.LANCZOS
                size = (max(1, round(pad_w * scale)), max(1, round(pad_h * scale)))
                photo = ImageTk.PhotoImage(padded.resize(size, resample),
                                           master=self.preview_canvas)
            except Exception as e:
                log.warning(f"Anteprima export non disponibile ({angle_data.file}): {e}")
        self._photo_cache[key] = photo
        return photo

    def _show_preview_at(self, ms):
        idx = bisect.bisect_right(self._segment_starts, ms) - 1
        angle_data = self._segments[idx][2] if 0 <= idx < len(self._segments) else None
        key = (angle_data.file, angle_data.mirrored) if angle_data is not None else None
        if key == self._shown_key:
            return
        self._shown_key = key

        c = self.preview_canvas
        c.delete('all')
        photo = self._preview_photo_for(angle_data) if angle_data is not None else None
        self._preview_photo = photo
        if photo is None:
            c.create_text(PREVIEW_SIZE / 2, PREVIEW_SIZE / 2, text="nessuna anteprima",
                          fill=TEXT_DIM, font=('Segoe UI', 8))
        else:
            c.create_image(PREVIEW_SIZE // 2, PREVIEW_SIZE // 2, image=photo)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _collect_rotation_frames(self):
        """Frame da esportare secondo il piano corrente (lo stesso che
        mostra l'anteprima). Ritorna (paths, durations, mirrored, skipped)."""
        paths, durations, mirrored = [], [], []
        skipped = 0
        for t0, t1, angle_data in _build_plan(self.blocks, self._x_ms):
            if angle_data is None:
                skipped += 1
                continue
            # Path, non str: load_and_pad_images usa p.name nel log di errore
            paths.append(Path(angle_data.file))
            durations.append(t1 - t0)
            mirrored.append(angle_data.mirrored)
        if skipped:
            log.warning(f"Export: {skipped} intervalli saltati (frame senza alcun angolo).")
        return paths, durations, mirrored, skipped

    def _on_export(self):
        # Ripulisce l'esito di un export precedente prima di validare il nuovo
        self._set_status("")
        fmt = self.format_var.get()
        angles = self._selected_angles()
        if not angles:
            messagebox.showwarning("Esporta",
                                   "L'angolo \"Da\" deve essere minore o uguale a \"A\".",
                                   parent=self.window)
            return
        if not self.blocks:
            messagebox.showwarning("Esporta", "Nessuna animazione selezionata.", parent=self.window)
            return
        if self._x_ms is None:
            messagebox.showwarning("Esporta",
                                   f"Durata X non valida: serve un valore tra 0 e "
                                   f"{_format_seconds(MAX_X_MS)} secondi.", parent=self.window)
            return
        if self.output_path is None:
            messagebox.showwarning("Esporta", "Scegli un file di destinazione.", parent=self.window)
            return
        out_path = self.output_path

        # Con l'alert attivo si esporta comunque, con taglio: nessuna conferma
        paths, durations, mirrored, skipped = self._collect_rotation_frames()
        if not paths:
            messagebox.showwarning("Esporta", "Nessun frame utilizzabile.", parent=self.window)
            return

        images = load_and_pad_images(paths)
        if len(images) != len(paths):
            # load_and_pad_images salta i file illeggibili: durate e mirror
            # non sarebbero più allineati ai frame, meglio fermarsi
            messagebox.showerror("Errore",
                                 f"{len(paths) - len(images)} frame non leggibili.\n"
                                 f"Dettagli nel log.", parent=self.window)
            return
        # Gli angoli mirrored riusano il file dell'angolo sorgente: vanno
        # ribaltati come fa la timeline nel viewer
        images = [img.transpose(Image.FLIP_LEFT_RIGHT) if m else img
                  for img, m in zip(images, mirrored)]

        try:
            export_animation(images, str(out_path), fmt, durations, loop=self.loop_var.get())
        except Exception as e:
            log.error(f"Export animazione fallito ({out_path}): {e}", exc_info=True)
            messagebox.showerror("Errore", f"Esportazione fallita:\n{e}", parent=self.window)
            return

        # Ricorda la cartella per il prossimo export
        self.settings.set("paths", "last_export_dir", str(out_path.parent))

        cut = self._x_ms % self._total_ms != 0
        codes = ",".join(e.code for e in self._selected_entries())
        log.info(f"Animazione esportata: {out_path} ({fmt}, animazioni {codes}, "
                 f"angoli {angles[0]}-{angles[-1]}, {len(self.blocks)} blocchi, "
                 f"X={self._x_ms}ms, {len(images)} frame{', con taglio' if cut else ''})")

        status = f"✓ Esportati {len(images)} frame in {out_path.name}"
        if skipped:
            status += f" — {skipped} intervalli saltati, vedi log"
        self._set_status(status, WARN_COLOR if skipped else OK_COLOR)

        if self.open_after_var.get():
            _open_folder_in_explorer(str(out_path.parent))

    def _close(self):
        if self._after_id is not None:
            try:
                self.window.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        try:
            self.window.grab_release()
        except Exception:
            pass
        self.window.destroy()
