#!/usr/bin/env python3
"""
Sprite Animation Tester / Converter
------------------------------------
Tool per sviluppatori di sprite (stile Doom/GZDoom): raccoglie sprite da
diverse fonti, li mostra come una vera ANIMAZIONE in-app (play/pause/stop/
loop) ed esporta la sequenza in un file animato (GIF o APNG) prima di
impacchettarla nel pk3.

Convenzione di naming supportata (stile Doom):
    BASE + LETTERA_FRAME[A-Z] + ROTAZIONE[1-8] (+ opzionale 2a coppia per mirror)
    Esempio: "PISG" + "A" + "1"  ->  PISGA1.png
             "PISG" + "A" + "1" + "A" + "8" -> PISGA1A8.png (frame mirrorato)

Formati di export:
    - GIF  : massima compatibilita', ma trasparenza binaria (niente alpha morbido)
    - APNG : trasparenza RGBA completa, ideale per sprite con antialiasing/glow

Dipendenze:
    pip install pillow
    pip install tkinterdnd2   (opzionale, abilita il drag & drop)

Per creare un eseguibile standalone (Windows/macOS/Linux):
    pip install pyinstaller
    pyinstaller --onefile --windowed sprite_converter.py
"""

import re
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

try:
    from PIL import Image, ImageTk
except ImportError:
    print("ERRORE: Pillow non installato. Esegui: pip install pillow")
    sys.exit(1)

# Drag & drop e' opzionale: se tkinterdnd2 non c'e', il tool funziona
# comunque, semplicemente senza quella scorciatoia.
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False

IMG_EXTENSIONS = (".png", ".jpg", ".jpeg")

# ---------------------------------------------------------------------------
# Logica pura (testabile senza GUI)
# ---------------------------------------------------------------------------

def build_pattern(code: str) -> re.Pattern:
    """Costruisce la regex per il naming stile Doom a partire dal codice base.
    BASE + [A-Z] + [0-8] + opzionale([A-Z] + [0-8]) + estensione
    """
    code_esc = re.escape(code)
    return re.compile(
        rf"^{code_esc}([A-Za-z])([0-8])([A-Za-z][0-8])?\.(png|jpe?g)$",
        re.IGNORECASE,
    )


def find_matching_files(folder: Path, code: str, recursive: bool = False):
    """Cerca in `folder` i file che rispettano BASE+lettera+rotazione."""
    pattern = build_pattern(code)
    files = folder.rglob("*") if recursive else folder.iterdir()
    matches = [f for f in files if f.is_file() and pattern.match(f.name)]
    return sort_sprite_files(matches, code)


def find_all_images(folder: Path, recursive: bool = False):
    """Prende tutte le immagini png/jpg in una cartella, senza filtro nome."""
    files = folder.rglob("*") if recursive else folder.iterdir()
    matches = [f for f in files if f.is_file() and f.suffix.lower() in IMG_EXTENSIONS]
    return sorted(matches, key=lambda p: p.name.lower())


def sort_sprite_files(files, code: str):
    """Ordina per lettera-frame poi per rotazione (naming Doom-style).
    Se il pattern non combacia (es. drag&drop libero), fallback su nome file.
    """
    pattern = build_pattern(code) if code else None

    def sort_key(path: Path):
        if pattern:
            m = pattern.match(path.name)
            if m:
                letter, digit = m.group(1).upper(), m.group(2)
                return (letter, digit)
        return (path.name.lower(), "")

    return sorted(files, key=sort_key)


def is_valid_code(code: str) -> bool:
    return 1 <= len(code) <= 6 and code.isalnum()


def get_app_dir() -> Path:
    """Cartella dello script (o dell'eseguibile, se compilato con pyinstaller).
    Usata come default per l'output, al posto della cwd che su Windows puo'
    risultare in posti inaspettati (es. C:\\WINDOWS\\system32) a seconda di
    come viene lanciato il programma.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def suggest_base_code(stem: str) -> str:
    """Estrae un possibile codice base da un nome file, togliendo solo
    l'ultima coppia lettera+rotazione (2 caratteri) se presente. Volutamente
    semplice: gestisce bene i casi comuni (CAPAA1 -> CAPA, WPN0A0 -> WPN0);
    sui frame mirrorati con doppia coppia (es. PISGA1A8) e' un'approssimazione,
    ma essendo solo un suggerimento per l'autocompletamento (non usato per
    filtrare la ricerca vera) va bene cosi'.
    """
    if len(stem) >= 3 and re.match(r"^[A-Za-z][0-8]$", stem[-2:]):
        return stem[:-2].upper()
    return stem.upper()


def collect_candidate_codes(folders):
    """Scansiona una o piu' cartelle e restituisce i codici base candidati,
    ordinati per frequenza (quanti file condividono quel codice) e poi
    alfabeticamente. Usato per l'autocompletamento del campo codice.
    """
    from collections import Counter
    seen_stems = set()
    for folder in folders:
        if not folder:
            continue
        folder = Path(folder)
        if not folder.exists() or not folder.is_dir():
            continue
        try:
            for f in folder.iterdir():
                if f.is_file() and f.suffix.lower() in IMG_EXTENSIONS:
                    seen_stems.add(f.stem)
        except OSError:
            continue
    counter = Counter(suggest_base_code(s) for s in seen_stems)
    return [c for c, _ in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))]


TICK_MS = 1000 / 35  # Doom: 35 tic al secondo


def load_frames_padded(paths, anchor: str = "bottom"):
    """Carica le immagini e le porta a un canvas RGBA uniforme (stessa
    dimensione per tutti i frame). E' un requisito per poter esportare
    un'animazione valida: GIF/APNG richiedono frame di size coerente,
    e in-game i viewmodel Doom-style vanno tenuti allineati sul pavimento.
    """
    imgs = []
    for p in paths:
        try:
            imgs.append(Image.open(p).convert("RGBA"))
        except Exception as e:
            print(f"Avviso: impossibile aprire {p.name}: {e}")

    if not imgs:
        return []

    max_w = max(i.width for i in imgs)
    max_h = max(i.height for i in imgs)

    padded = []
    for img in imgs:
        canvas = Image.new("RGBA", (max_w, max_h), (0, 0, 0, 0))
        x = (max_w - img.width) // 2
        y = (max_h - img.height) if anchor == "bottom" else (max_h - img.height) // 2
        canvas.paste(img, (x, y), img)
        padded.append(canvas)

    return padded


def export_animation(frames, out_path: Path, fmt: str, duration_ms: int, loop: bool):
    """Salva i frame come animazione. fmt: 'GIF' o 'APNG'."""
    if not frames:
        raise ValueError("Nessun frame da esportare")

    loop_count = 0 if loop else 1  # Pillow: 0 = loop infinito

    if fmt == "APNG":
        frames[0].save(
            out_path, save_all=True, append_images=frames[1:],
            duration=duration_ms, loop=loop_count, disposal=2,
        )
    elif fmt == "GIF":
        # GIF non supporta alpha morbido: quantizziamo su palette con un
        # singolo indice trasparente (trasparenza binaria, come da spec Doom).
        gif_frames = []
        for f in frames:
            quantized = f.convert("RGBA")
            alpha = quantized.split()[-1]
            mask = alpha.point(lambda a: 255 if a > 127 else 0)
            rgb = quantized.convert("RGB")
            pal = rgb.convert("P", palette=Image.ADAPTIVE, colors=255)
            pal.paste(255, mask=Image.eval(mask, lambda a: 255 - a))
            gif_frames.append(pal)
        gif_frames[0].save(
            out_path, save_all=True, append_images=gif_frames[1:],
            duration=duration_ms, loop=loop_count, disposal=2,
            transparency=255,
        )
    else:
        raise ValueError(f"Formato non supportato: {fmt}")


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

class SpriteConverterApp:

    def __init__(self, root):
        self.root = root
        self.root.title("Sprite Animation Tester")
        self.root.configure(bg="white")
        self.root.geometry("880x680")
        self.root.minsize(760, 600)

        self.mode = tk.StringVar(value="code")
        self.code_var = tk.StringVar()
        self.folder_var = tk.StringVar()
        self.folder_filter_var = tk.BooleanVar(value=True)
        self.manual_files = []  # usata da opzione 3 + drag&drop
        self.out_folder_var = tk.StringVar(value=str(get_app_dir()))
        self.out_name_var = tk.StringVar(value="sprite_anim")
        self.format_var = tk.StringVar(value="APNG")
        self.speed_var = tk.IntVar(value=120)  # ms per frame (unita' canonica interna)
        self.loop_var = tk.BooleanVar(value=True)

        self.frames = []          # lista di PIL.Image RGBA (padded, uniformi)
        self.matched_paths = []
        self.is_playing = False
        self.current_idx = 0
        self._after_id = None
        self._candidate_codes = []  # per l'autocompletamento del codice

        self._build_ui()

    # ---------------- UI construction ----------------

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="white")
        style.configure("TLabel", background="white")
        style.configure("TRadiobutton", background="white")
        style.configure("TCheckbutton", background="white")

        # ---- Finestra scorrevole ----
        # Tutto il contenuto vive dentro un canvas scrollabile: se la finestra
        # e' troppo piccola per mostrare tutto (es. schermi piccoli), compare
        # una scrollbar invece di tagliare via pezzi dell'interfaccia (come
        # il tasto Esporta che prima poteva finire fuori dalla vista).
        outer = tk.Canvas(self.root, bg="white", highlightthickness=0)
        vscroll = ttk.Scrollbar(self.root, orient="vertical", command=outer.yview)
        outer.configure(yscrollcommand=vscroll.set)
        outer.pack(side="left", fill="both", expand=True)
        vscroll.pack(side="right", fill="y")

        page = ttk.Frame(outer)
        page_window = outer.create_window((0, 0), window=page, anchor="nw")

        def _sync_scrollregion(event=None):
            outer.configure(scrollregion=outer.bbox("all"))

        def _sync_width(event):
            outer.itemconfig(page_window, width=event.width)

        page.bind("<Configure>", _sync_scrollregion)
        outer.bind("<Configure>", _sync_width)

        def _on_mousewheel(event):
            delta = event.delta
            if delta:
                outer.yview_scroll(int(-delta / 120) or (-1 if delta > 0 else 1), "units")
            elif event.num == 4:
                outer.yview_scroll(-1, "units")
            elif event.num == 5:
                outer.yview_scroll(1, "units")

        outer.bind_all("<MouseWheel>", _on_mousewheel)
        outer.bind_all("<Button-4>", _on_mousewheel)
        outer.bind_all("<Button-5>", _on_mousewheel)

        title = tk.Label(page, text="Anteprima per animazioni", bg="white",
                          font=("Segoe UI", 16, "bold"))
        title.pack(pady=(14, 2))
        subtitle = tk.Label(
            page,
            text="| Yagor Studio |",
            bg="white", fg="#666666", font=("Segoe UI", 9),
        )
        subtitle.pack(pady=(0, 10))

        main = ttk.Frame(page)
        main.pack(fill="both", expand=True, padx=16, pady=6)

        # ---- Sorgente ----
        source_box = ttk.LabelFrame(main, text="1. Fonte sprite")
        source_box.pack(fill="x", pady=(0, 8))

        ttk.Radiobutton(source_box, text="Codice sprite (cerca in una cartella)",
                         variable=self.mode, value="code",
                         command=self._refresh_mode).grid(row=0, column=0, sticky="w", padx=8, pady=(6, 0))
        ttk.Radiobutton(source_box, text="Cartella (unisci tutti i file)",
                         variable=self.mode, value="folder",
                         command=self._refresh_mode).grid(row=1, column=0, sticky="w", padx=8)
        ttk.Radiobutton(source_box, text="Selezione manuale immagini",
                         variable=self.mode, value="manual",
                         command=self._refresh_mode).grid(row=2, column=0, sticky="w", padx=8)

        # Opzione 1: codice
        self.code_frame = ttk.Frame(source_box)
        code_row = ttk.Frame(self.code_frame)
        code_row.pack(fill="x")
        ttk.Label(code_row, text="Codice (max 6, alfanumerico):").pack(side="left")
        code_entry = ttk.Entry(code_row, textvariable=self.code_var, width=8)
        code_entry.pack(side="left", padx=6)
        code_entry.bind("<KeyRelease>", self._on_code_typed)
        ttk.Label(code_row, text="Cerca: CODICE + [A-Z] + [0-8]  es. PISGA1.png",
                  foreground="#666666").pack(side="left", padx=8)
        ttk.Button(code_row, text="Scegli cartella...",
                   command=self._pick_code_folder).pack(side="left", padx=8)
        self.code_folder_lbl = ttk.Label(code_row, text="(nessuna cartella)", foreground="#666666")
        self.code_folder_lbl.pack(side="left")

        # Suggerimenti live: mentre scrivi, mostra i codici gia' presenti
        # nella cartella (script e/o cartella scelta) che iniziano cosi'.
        sugg_row = ttk.Frame(self.code_frame)
        sugg_row.pack(fill="x", pady=(4, 0))
        ttk.Label(sugg_row, text="Suggerimenti:", foreground="#999999").pack(side="left")
        self.suggestion_listbox = tk.Listbox(sugg_row, height=1, width=50, activestyle="none",
                                              exportselection=False, bg="#fafafa", relief="flat")
        self.suggestion_listbox.pack(side="left", padx=6, fill="x", expand=True)
        self.suggestion_listbox.bind("<<ListboxSelect>>", self._on_suggestion_pick)

        # Opzione 2: cartella
        self.folder_frame = ttk.Frame(source_box)
        ttk.Button(self.folder_frame, text="Scegli cartella...",
                   command=self._pick_merge_folder).pack(side="left")
        self.folder_lbl = ttk.Label(self.folder_frame, text="(nessuna cartella)", foreground="#666666")
        self.folder_lbl.pack(side="left", padx=8)
        ttk.Checkbutton(self.folder_frame, text="Filtra per codice (come opzione 1)",
                         variable=self.folder_filter_var,
                         command=self._refresh_mode).pack(side="left", padx=12)
        self.folder_code_entry = ttk.Entry(self.folder_frame, textvariable=self.code_var, width=8)
        self.folder_code_entry.pack(side="left")

        # Opzione 3: manuale
        self.manual_frame = ttk.Frame(source_box)
        ttk.Button(self.manual_frame, text="Scegli immagini...",
                   command=self._pick_manual_files).pack(side="left")
        ttk.Button(self.manual_frame, text="Svuota selezione",
                   command=self._clear_manual_files).pack(side="left", padx=8)
        self.manual_count_lbl = ttk.Label(self.manual_frame, text="0 file selezionati",
                                           foreground="#666666")
        self.manual_count_lbl.pack(side="left", padx=8)

        for f in (self.code_frame, self.folder_frame, self.manual_frame):
            f.grid(row=0, column=1, sticky="w", padx=8, pady=6)
        source_box.columnconfigure(1, weight=1)

        # ---- Drag & drop ----
        dnd_text = ("Trascina qui i file immagine" if DND_AVAILABLE
                    else "Drag & drop non disponibile (installa tkinterdnd2)")
        self.dnd_area = tk.Label(
            main, text=dnd_text, bg="#fafafa", fg="#888888",
            relief="ridge", bd=1, height=2, font=("Segoe UI", 9, "italic"),
        )
        self.dnd_area.pack(fill="x", pady=(0, 8))
        if DND_AVAILABLE:
            self.dnd_area.drop_target_register(DND_FILES)
            self.dnd_area.dnd_bind("<<Drop>>", self._on_drop)

        # ---- Carica frame ----
        action_row = ttk.Frame(main)
        action_row.pack(fill="x", pady=(0, 6))
        ttk.Button(action_row, text="Carica frame",
                   command=self.load_frames).pack(side="left")
        self.status_lbl = ttk.Label(action_row, text="Nessun frame caricato",
                                     foreground="#666666")
        self.status_lbl.pack(side="left", padx=12)

        # ---- Anteprima animata ----
        preview_box = ttk.LabelFrame(main, text="2. Anteprima animata")
        # fill="x" (non "both"/expand=True): il player prende solo lo spazio
        # che gli serve, senza "mangiarsi" lo spazio verticale che serve alla
        # sezione 3 sotto (era la causa del tasto Esporta fuori dalla finestra).
        preview_box.pack(fill="x", pady=(0, 8))

        self.canvas = tk.Canvas(preview_box, bg="#eeeeee", highlightthickness=0, height=144)
        self.canvas.pack(side="top", fill="x", padx=8, pady=(8, 4))

        player_row = ttk.Frame(preview_box)
        player_row.pack(fill="x", padx=8, pady=(0, 4))

        self.play_btn = ttk.Button(player_row, text="\u25B6 Play", command=self._play, width=9)
        self.play_btn.pack(side="left")
        self.pause_btn = ttk.Button(player_row, text="\u23F8 Pausa", command=self._pause, width=9)
        self.pause_btn.pack(side="left", padx=4)
        self.stop_btn = ttk.Button(player_row, text="\u23F9 Stop", command=self._stop, width=9)
        self.stop_btn.pack(side="left", padx=4)
        ttk.Checkbutton(player_row, text="Loop", variable=self.loop_var).pack(side="left", padx=12)

        ttk.Label(player_row, text="Velocita' (ms/frame):").pack(side="left", padx=(12, 4))
        speed_spin = ttk.Spinbox(player_row, from_=20, to=2000, increment=10,
                                  textvariable=self.speed_var, width=6,
                                  command=self._update_time_labels)
        speed_spin.pack(side="left")
        speed_spin.bind("<KeyRelease>", lambda e: self._update_time_labels())

        self.frame_lbl = ttk.Label(player_row, text="Frame: -/-", foreground="#666666")
        self.frame_lbl.pack(side="right")

        # Riga tempo: secondi (contatore vivo come quello dei frame) + tick
        # Doom (35 tic/secondo) + durata totale della sequenza.
        time_row = ttk.Frame(preview_box)
        time_row.pack(fill="x", padx=8, pady=(0, 8))
        self.time_lbl = ttk.Label(time_row, text="Tempo: -/-  ·  Durata totale: -",
                                   foreground="#666666")
        self.time_lbl.pack(side="left")
        self.tick_lbl = ttk.Label(time_row, text="", foreground="#999999")
        self.tick_lbl.pack(side="right")

        # ---- Output ----
        out_box = ttk.LabelFrame(main, text="3. Esporta animazione")
        out_box.pack(fill="x")

        # Le colonne 0-2 (label+campo+sfoglia) occupano circa 3/4 della riga,
        # il tasto Esporta sta di lato nella colonna 3, ancorato in alto cosi'
        # resta sempre visibile in cima alla sezione invece che in fondo.
        ttk.Label(out_box, text="Cartella destinazione:").grid(row=0, column=0, sticky="w", padx=8, pady=6)
        ttk.Entry(out_box, textvariable=self.out_folder_var, width=32).grid(row=0, column=1, sticky="we", padx=4)
        ttk.Button(out_box, text="Sfoglia...", command=self._pick_output_folder).grid(row=0, column=2, padx=(4, 12))

        ttk.Label(out_box, text="Nome file:").grid(row=1, column=0, sticky="w", padx=8, pady=6)
        ttk.Entry(out_box, textvariable=self.out_name_var, width=20).grid(row=1, column=1, sticky="w", padx=4)

        format_row = ttk.Frame(out_box)
        format_row.grid(row=1, column=2, sticky="w", padx=(4, 12))
        ttk.Radiobutton(format_row, text="APNG (alpha completo)",
                         variable=self.format_var, value="APNG").pack(anchor="w")
        ttk.Radiobutton(format_row, text="GIF (compatibilita')",
                         variable=self.format_var, value="GIF").pack(anchor="w")

        export_btn = ttk.Button(out_box, text="Esporta\nanimazione",
                                 command=self.export_animation_file)
        export_btn.grid(row=0, column=3, rowspan=2, sticky="ns", padx=8, pady=6)

        out_box.columnconfigure(1, weight=1)

        self._refresh_mode()
        self._refresh_candidates()
        self._update_time_labels()

    # ---------------- Mode switching ----------------

    def _refresh_mode(self):
        for f in (self.code_frame, self.folder_frame, self.manual_frame):
            f.grid_remove()
        m = self.mode.get()
        if m == "code":
            self.code_frame.grid()
        elif m == "folder":
            self.folder_frame.grid()
            self.folder_code_entry.configure(
                state="normal" if self.folder_filter_var.get() else "disabled")
        elif m == "manual":
            self.manual_frame.grid()

    def _enforce_code_limit(self, event=None):
        v = self.code_var.get()
        v = re.sub(r"[^A-Za-z0-9]", "", v)[:6]
        self.code_var.set(v)

    # ---------------- Autocompletamento codice ----------------

    def _refresh_candidates(self):
        """Rilegge i codici candidati da: cartella dello script + cartella
        eventualmente selezionata. Chiamata all'avvio e ogni volta che si
        sceglie una cartella diversa."""
        folders = [get_app_dir()]
        if self.folder_var.get():
            folders.append(self.folder_var.get())
        self._candidate_codes = collect_candidate_codes(folders)
        self._update_code_suggestions()

    def _on_code_typed(self, event=None):
        self._enforce_code_limit()
        self._update_code_suggestions()

    def _update_code_suggestions(self):
        prefix = self.code_var.get().strip().upper()
        if prefix:
            matches = [c for c in self._candidate_codes if c.startswith(prefix) and c != prefix]
        else:
            matches = self._candidate_codes
        matches = matches[:8]
        self.suggestion_listbox.delete(0, "end")
        for c in matches:
            self.suggestion_listbox.insert("end", c)
        self.suggestion_listbox.configure(height=max(1, min(len(matches), 4)))

    def _on_suggestion_pick(self, event=None):
        sel = self.suggestion_listbox.curselection()
        if not sel:
            return
        code = self.suggestion_listbox.get(sel[0])
        self.code_var.set(code)
        self._update_code_suggestions()

    # ---------------- Source pickers ----------------

    def _pick_code_folder(self):
        d = filedialog.askdirectory(title="Cartella dove cercare gli sprite",
                                     initialdir=str(get_app_dir()))
        if d:
            self.folder_var.set(d)
            self.code_folder_lbl.config(text=Path(d).name)
            self._refresh_candidates()

    def _pick_merge_folder(self):
        d = filedialog.askdirectory(title="Cartella da unire",
                                     initialdir=str(get_app_dir()))
        if d:
            self.folder_var.set(d)
            self.folder_lbl.config(text=Path(d).name)
            self._refresh_candidates()

    def _pick_manual_files(self):
        files = filedialog.askopenfilenames(
            title="Seleziona immagini",
            filetypes=[("Immagini", "*.png *.jpg *.jpeg")],
        )
        if files:
            self.manual_files.extend(Path(f) for f in files)
            self._update_manual_count()

    def _clear_manual_files(self):
        self.manual_files = []
        self._update_manual_count()

    def _update_manual_count(self):
        self.manual_count_lbl.config(text=f"{len(self.manual_files)} file selezionati")

    def _on_drop(self, event):
        raw = event.data
        paths = self.root.tk.splitlist(raw)
        added = 0
        for p in paths:
            path = Path(p)
            if path.is_file() and path.suffix.lower() in IMG_EXTENSIONS:
                self.manual_files.append(path)
                added += 1
        if added:
            self.mode.set("manual")
            self._refresh_mode()
            self._update_manual_count()
            self.status_lbl.config(text=f"{added} immagini aggiunte via drag & drop")

    def _pick_output_folder(self):
        d = filedialog.askdirectory(title="Cartella di destinazione",
                                     initialdir=self.out_folder_var.get() or str(get_app_dir()))
        if d:
            self.out_folder_var.set(d)

    # ---------------- Core actions ----------------

    def _gather_paths(self):
        m = self.mode.get()
        code = self.code_var.get().strip()

        if m == "code":
            if not self.folder_var.get():
                messagebox.showwarning("Attenzione", "Scegli prima una cartella.")
                return []
            if not is_valid_code(code):
                messagebox.showwarning("Attenzione", "Inserisci un codice alfanumerico (1-6 caratteri).")
                return []
            return find_matching_files(Path(self.folder_var.get()), code)

        if m == "folder":
            if not self.folder_var.get():
                messagebox.showwarning("Attenzione", "Scegli prima una cartella.")
                return []
            if self.folder_filter_var.get():
                if not is_valid_code(code):
                    messagebox.showwarning("Attenzione", "Inserisci un codice valido per il filtro.")
                    return []
                return find_matching_files(Path(self.folder_var.get()), code)
            return find_all_images(Path(self.folder_var.get()))

        if m == "manual":
            if not self.manual_files:
                messagebox.showwarning("Attenzione", "Nessuna immagine selezionata.")
                return []
            return sort_sprite_files(self.manual_files, code) if code else self.manual_files

        return []

    def load_frames(self):
        self._stop()
        paths = self._gather_paths()
        self.matched_paths = paths
        if not paths:
            self.status_lbl.config(text="Nessun file trovato")
            self.frames = []
            self.canvas.delete("all")
            self.frame_lbl.config(text="Frame: -/-")
            self._update_time_labels()
            return

        self.frames = load_frames_padded(paths)
        if not self.frames:
            self.status_lbl.config(text="Errore nel caricamento dei frame")
            return

        self.current_idx = 0
        w, h = self.frames[0].size
        self.status_lbl.config(
            text=f"{len(self.frames)} frame caricati · {w}x{h}px  "
                 f"({', '.join(p.name for p in paths[:6])}{'...' if len(paths) > 6 else ''})"
        )
        self._show_frame(0)

    # ---------------- Player ----------------

    def _play(self):
        if not self.frames:
            messagebox.showwarning("Attenzione", "Carica prima dei frame.")
            return
        if self.is_playing:
            return
        self.is_playing = True
        self._tick()

    def _pause(self):
        self.is_playing = False
        if self._after_id is not None:
            self.root.after_cancel(self._after_id)
            self._after_id = None

    def _stop(self):
        self._pause()
        self.current_idx = 0
        if self.frames:
            self._show_frame(0)
        else:
            self._update_time_labels()

    def _tick(self):
        if not self.is_playing or not self.frames:
            return
        self._show_frame(self.current_idx)
        next_idx = self.current_idx + 1
        if next_idx >= len(self.frames):
            if self.loop_var.get():
                next_idx = 0
            else:
                self.is_playing = False
                return
        self.current_idx = next_idx
        delay = max(20, int(self.speed_var.get()))
        self._after_id = self.root.after(delay, self._tick)

    def _show_frame(self, idx):
        frame = self.frames[idx]
        canvas_w = max(self.canvas.winfo_width(), 200)
        canvas_h = max(self.canvas.winfo_height(), 200)
        scale = min((canvas_w - 20) / frame.width, (canvas_h - 20) / frame.height, 4.0)
        scale = max(scale, 0.05)
        disp_w = max(1, int(frame.width * scale))
        disp_h = max(1, int(frame.height * scale))
        disp_img = frame.resize((disp_w, disp_h), Image.NEAREST)

        checker = self._make_checker(disp_w, disp_h)
        checker.paste(disp_img, (0, 0), disp_img)

        self._tk_preview_img = ImageTk.PhotoImage(checker)
        self.canvas.delete("all")
        cx, cy = canvas_w // 2, canvas_h // 2
        self.canvas.create_image(cx, cy, anchor="center", image=self._tk_preview_img)
        self.frame_lbl.config(text=f"Frame: {idx + 1}/{len(self.frames)}")
        self._update_time_labels(current_idx=idx)

    def _update_time_labels(self, current_idx=None):
        """Aggiorna i contatori di tempo: secondi trascorsi/totali e tick
        Doom equivalenti (35 tic/secondo), oltre alla durata totale della
        sequenza alla velocita' attualmente impostata."""
        ms_per_frame = max(20, int(self.speed_var.get() or 20))
        n = len(self.frames)
        total_ms = ms_per_frame * n
        total_s = total_ms / 1000

        if n and current_idx is not None:
            elapsed_s = (ms_per_frame * current_idx) / 1000
            time_txt = f"Tempo: {elapsed_s:.2f}s / {total_s:.2f}s  ·  Durata totale: {total_s:.2f}s"
        else:
            time_txt = f"Tempo: -/-  ·  Durata totale: {total_s:.2f}s" if n else "Tempo: -/-  ·  Durata totale: -"

        self.time_lbl.config(text=time_txt)

        tick_per_frame = ms_per_frame / TICK_MS
        self.tick_lbl.config(
            text=f"\u2248 {tick_per_frame:.1f} tick/frame  ·  {total_ms/TICK_MS:.1f} tick totali"
            if n else ""
        )

    @staticmethod
    def _make_checker(w, h, cell=8):
        base = Image.new("RGBA", (w, h), (255, 255, 255, 255))
        c1, c2 = (210, 210, 210, 255), (240, 240, 240, 255)
        for y in range(0, h, cell):
            for x in range(0, w, cell):
                color = c1 if ((x // cell) + (y // cell)) % 2 == 0 else c2
                for yy in range(y, min(y + cell, h)):
                    for xx in range(x, min(x + cell, w)):
                        base.putpixel((xx, yy), color)
        return base

    # ---------------- Export ----------------

    def export_animation_file(self):
        if not self.frames:
            self.load_frames()
            if not self.frames:
                messagebox.showwarning("Attenzione", "Carica prima dei frame.")
                return

        out_folder = Path(self.out_folder_var.get())
        name = self.out_name_var.get().strip() or "sprite_anim"
        if not out_folder.exists():
            messagebox.showerror("Errore", "Cartella di destinazione non valida.")
            return

        fmt = self.format_var.get()
        ext = ".png" if fmt == "APNG" else ".gif"
        out_path = out_folder / f"{name}{ext}"

        try:
            export_animation(self.frames, out_path, fmt,
                              duration_ms=max(20, int(self.speed_var.get())),
                              loop=self.loop_var.get())
        except Exception as e:
            messagebox.showerror("Errore", f"Impossibile salvare: {e}")
            return

        messagebox.showinfo("Fatto", f"Animazione salvata in:\n{out_path}")
        self.status_lbl.config(text=f"Esportato: {out_path.name}")


def main():
    root = TkinterDnD.Tk() if DND_AVAILABLE else tk.Tk()
    app = SpriteConverterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()