# sprite_studio/ui_spritesheet.py
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

from PIL import Image, ImageTk

from .models import ProfileData, AnimationData, FrameGroup, AngleData
from .project_manager import ProjectManager
from .constants import DEFAULT_DURATION_MS

class PlaceholderEntry(tk.Entry):
    """Entry con placeholder visivo, stile dark coerente con il resto dell'app.
    Il placeholder NON finisce mai nella textvariable: la variabile resta vuota
    finché l'utente non digita."""

    BG = '#3a3a3a'
    FG = '#ffffff'
    FG_PLACEHOLDER = '#777777'

    def __init__(self, parent, textvariable=None, placeholder="", **kwargs):
        kwargs.setdefault('bg', self.BG)
        kwargs.setdefault('fg', self.FG_PLACEHOLDER)
        kwargs.setdefault('relief', 'flat')
        kwargs.setdefault('insertbackground', 'white')
        kwargs.setdefault('highlightthickness', 0)
        super().__init__(parent, **kwargs)

        self._var = textvariable
        self._placeholder = placeholder
        self._showing_placeholder = False

        self.bind('<FocusIn>', self._on_focus_in)
        self.bind('<FocusOut>', self._on_focus_out)
        self.bind('<KeyRelease>', self._on_key)
        self._show_placeholder()

    def _show_placeholder(self):
        self.delete(0, 'end')
        self.insert(0, self._placeholder)
        self.configure(fg=self.FG_PLACEHOLDER)
        self._showing_placeholder = True

    def _on_focus_in(self, event):
        if self._showing_placeholder:
            self.delete(0, 'end')
            self.configure(fg=self.FG)
            self._showing_placeholder = False

    def _on_focus_out(self, event):
        val = self.get().strip()
        if not val:
            self._show_placeholder()
            if self._var is not None:
                self._var.set("")

    def _on_key(self, event):
        if self._var is not None and not self._showing_placeholder:
            self._var.set(self.get())

class SpritesheetWindow:
    """Finestra import/export da spritesheet.

    Concetti separati:
      - GRIGLIA VISIVA: Righe × Colonne. Serve solo a disegnare le celle sopra l'immagine.
      - NUMERAZIONE: Numero Frame × Numero Angoli. Definisce quanti file generare.
      - ORDINE: ANGOLO→FRAME (angolo cambia per primo) oppure FRAME→ANGOLO.
    """

    ZOOM_LEVELS = [0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0]
    ZOOM_LABELS = ["25%", "50%", "75%", "100%", "150%", "200%", "300%", "400%", "600%", "800%"]

    # Valori interni per l'ordine
    ORDER_ANGLE_FRAME = "ANGOLO→FRAME"
    ORDER_FRAME_ANGLE = "FRAME→ANGOLO"

    def __init__(self, parent, project, on_import=None):
        self.parent = parent
        self.project = project
        self.on_import = on_import

        self.image = None
        self.image_path = None
        self.tk_image = None
        self.current_scale = 1.0
        self._prev_total_cells = None

        # --- Griglia visiva ---
        self.grid_rows_var = tk.IntVar(value=1)
        self.grid_cols_var = tk.IntVar(value=1)
        self.off_x_var = tk.IntVar(value=0)
        self.off_y_var = tk.IntVar(value=0)
        self.pad_x_var = tk.IntVar(value=0)
        self.pad_y_var = tk.IntVar(value=0)
        self.show_grid_var = tk.BooleanVar(value=True)
        self.show_numbers_var = tk.BooleanVar(value=True)
        self.start_cell_var = tk.IntVar(value=1)
        self.end_cell_var = tk.IntVar(value=1)

        # --- Numerazione / esportazione ---
        self.num_frames_var = tk.IntVar(value=1)
        self.num_angles_var = tk.IntVar(value=1)
        self.order_var = tk.StringVar(value=self.ORDER_ANGLE_FRAME)

        # --- Esportazione ---
        self.dest_var = tk.StringVar(value=str(Path.cwd()))
        self.sprite_prefix_var = tk.StringVar(value="AB")
        self.anim_prefix_var = tk.StringVar(value="CD")
        self.start_letter_var = tk.StringVar(value="A")
        self.start_angle_var = tk.IntVar(value=1)
        self.import_var = tk.BooleanVar(value=False)
        self.zoom_var = tk.StringVar(value="Fit")
        self.info_var = tk.StringVar(value="Nessuna immagine caricata")

        # --- Finestra ---
        self.window = tk.Toplevel(parent)
        self.window.title("Spritesheet - Import/Export")
        self.window.geometry("700x820")
        self.window.minsize(560, 660)
        self.window.configure(bg='#2b2b2b')
        self.window.transient(parent)
        self.window.focus_force()

        self._build_ui()
        self._setup_traces()

        self.window.after(150, self._render_canvas)

    # =================================================================
    # HELPERS
    # =================================================================

    def _safe_int(self, var, default=1):
        try:
            return int(var.get())
        except (tk.TclError, ValueError):
            return default

    def _safe_str(self, var, default=""):
        try:
            v = var.get()
            return v if v is not None else default
        except tk.TclError:
            return default

    # =================================================================
    # UI
    # =================================================================

    def _build_ui(self):
        # --- Barra superiore ---
        top = ttk.Frame(self.window)
        top.pack(fill='x', padx=8, pady=3)

        ttk.Button(top, text="Apri immagine…", command=self._open_image).pack(side='left')
        self.filename_lbl = ttk.Label(top, text="Nessun file", foreground='#888888')
        self.filename_lbl.pack(side='left', padx=10)

        ttk.Label(top, text="Zoom:").pack(side='left', padx=(20, 3))
        self.zoom_combo = ttk.Combobox(top, textvariable=self.zoom_var, state='readonly',
                                        values=["Fit"] + self.ZOOM_LABELS, width=6)
        self.zoom_combo.pack(side='left')
        self.zoom_combo.bind('<<ComboboxSelected>>', lambda e: self._render_canvas())

        ttk.Button(top, text="−", width=3, command=self._zoom_out).pack(side='left', padx=(4, 1))
        ttk.Button(top, text="+", width=3, command=self._zoom_in).pack(side='left')

        # --- Canvas con scrollbar ---
        canvas_container = ttk.Frame(self.window)
        canvas_container.pack(fill='both', expand=True, padx=8, pady=2)

        self.canvas = tk.Canvas(canvas_container, bg='#1a1a1a',
                                highlightthickness=1, highlightbackground='#444444')
        h_scroll = ttk.Scrollbar(canvas_container, orient='horizontal', command=self.canvas.xview)
        v_scroll = ttk.Scrollbar(canvas_container, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)

        self.canvas.grid(row=0, column=0, sticky='nsew')
        v_scroll.grid(row=0, column=1, sticky='ns')
        h_scroll.grid(row=1, column=0, sticky='ew')
        canvas_container.rowconfigure(0, weight=1)
        canvas_container.columnconfigure(0, weight=1)

        # --- GRIGLIA VISIVA ---
        grid_frame = ttk.LabelFrame(self.window, text="Griglia visiva", padding=4)
        grid_frame.pack(fill='x', padx=8, pady=2)

        r1 = ttk.Frame(grid_frame)
        r1.pack(fill='x', pady=1)

        ttk.Label(r1, text="Righe:").pack(side='left')
        ttk.Spinbox(r1, from_=1, to=64, width=4,
                    textvariable=self.grid_rows_var).pack(side='left', padx=(2, 15))

        ttk.Label(r1, text="Colonne:").pack(side='left')
        ttk.Spinbox(r1, from_=1, to=64, width=4,
                    textvariable=self.grid_cols_var).pack(side='left', padx=(2, 15))

        ttk.Label(r1, text="Offset X:").pack(side='left')
        ttk.Spinbox(r1, from_=-500, to=500, width=5,
                    textvariable=self.off_x_var).pack(side='left', padx=(2, 15))

        ttk.Label(r1, text="Offset Y:").pack(side='left')
        ttk.Spinbox(r1, from_=-500, to=500, width=5,
                    textvariable=self.off_y_var).pack(side='left', padx=(2, 15))

        ttk.Label(r1, text="Pad X:").pack(side='left')
        ttk.Spinbox(r1, from_=0, to=200, width=4,
                    textvariable=self.pad_x_var).pack(side='left', padx=(2, 15))

        ttk.Label(r1, text="Pad Y:").pack(side='left')
        ttk.Spinbox(r1, from_=0, to=200, width=4,
                    textvariable=self.pad_y_var).pack(side='left', padx=(2, 0))

        r2 = ttk.Frame(grid_frame)
        r2.pack(fill='x', pady=2)

        ttk.Checkbutton(r2, text="Mostra griglia",
                        variable=self.show_grid_var).pack(side='left', padx=(0, 12))
        ttk.Checkbutton(r2, text="Mostra etichette",
                        variable=self.show_numbers_var).pack(side='left', padx=(0, 12))

        ttk.Label(r2, text="Da cella:").pack(side='left', padx=(20, 2))
        ttk.Spinbox(r2, from_=1, to=9999, width=5,
                    textvariable=self.start_cell_var).pack(side='left')
        ttk.Label(r2, text="A cella:").pack(side='left', padx=(12, 2))
        ttk.Spinbox(r2, from_=1, to=9999, width=5,
                    textvariable=self.end_cell_var).pack(side='left', padx=(0, 12))

        ttk.Button(r2, text="Reset griglia",
                   command=self._reset_grid).pack(side='left')

        # --- NUMERAZIONE ---
        num_frame = ttk.LabelFrame(self.window, text="Numerazione", padding=4)
        num_frame.pack(fill='x', padx=8, pady=2)

        nr1 = ttk.Frame(num_frame)
        nr1.pack(fill='x', pady=1)

        ttk.Label(nr1, text="Numero Frame (lettere):").pack(side='left')
        ttk.Spinbox(nr1, from_=1, to=26, width=4,
                    textvariable=self.num_frames_var).pack(side='left', padx=(2, 15))

        ttk.Label(nr1, text="Numero Angoli:").pack(side='left')
        ttk.Spinbox(nr1, from_=1, to=64, width=4,
                    textvariable=self.num_angles_var).pack(side='left', padx=(2, 15))

        ttk.Label(nr1, text="Ordine:").pack(side='left')
        self.order_combo = ttk.Combobox(
            nr1, textvariable=self.order_var, state='readonly', width=16,
            values=[self.ORDER_ANGLE_FRAME, self.ORDER_FRAME_ANGLE]
        )
        self.order_combo.pack(side='left', padx=(2, 0))

        # --- ESPORTAZIONE ---
        exp_frame = ttk.LabelFrame(self.window, text="Esportazione", padding=4)
        exp_frame.pack(fill='x', padx=8, pady=2)

        d_row = ttk.Frame(exp_frame)
        d_row.pack(fill='x', pady=1)
        ttk.Label(d_row, text="Destinazione:").pack(side='left')
        ttk.Entry(d_row, textvariable=self.dest_var).pack(side='left', fill='x', expand=True, padx=4)
        ttk.Button(d_row, text="Sfoglia…", command=self._browse_dest).pack(side='left')

        p_row = ttk.Frame(exp_frame)
        p_row.pack(fill='x', pady=1)

        ttk.Label(p_row, text="Prefisso Sprite:").pack(side='left')
        PlaceholderEntry(p_row, textvariable=self.sprite_prefix_var,
                         placeholder="AB", width=6).pack(side='left', padx=(2, 15))

        ttk.Label(p_row, text="Prefisso Animazione:").pack(side='left')
        PlaceholderEntry(p_row, textvariable=self.anim_prefix_var,
                         placeholder="CD", width=6).pack(side='left', padx=(2, 15))

        ttk.Label(p_row, text="Lettera iniziale:").pack(side='left')
        ttk.Entry(p_row, textvariable=self.start_letter_var, width=3).pack(side='left', padx=(2, 15))

        ttk.Label(p_row, text="Angolo iniziale:").pack(side='left')
        ttk.Spinbox(p_row, from_=0, to=8, width=3,
                    textvariable=self.start_angle_var).pack(side='left', padx=2)

        i_row = ttk.Frame(exp_frame)
        i_row.pack(fill='x', pady=1)
        ttk.Checkbutton(i_row,
                        text="Importa direttamente nel progetto (crea/aggiorna libreria)",
                        variable=self.import_var).pack(side='left')

        # --- Barra pulsanti ---
        btn_bar = ttk.Frame(self.window)
        btn_bar.pack(fill='x', padx=8, pady=4)

        ttk.Button(btn_bar, text="Esporta frame", command=self._export_frames).pack(side='left')
        ttk.Button(btn_bar, text="Chiudi", command=self.window.destroy).pack(side='left', padx=6)
        ttk.Label(btn_bar, textvariable=self.info_var, foreground='#888888').pack(side='right')

    def _setup_traces(self):
        # Griglia visiva → re-render + eventuale aggiornamento range
        for var in (self.grid_rows_var, self.grid_cols_var,
                    self.off_x_var, self.off_y_var,
                    self.pad_x_var, self.pad_y_var):
            var.trace_add('write', self._on_grid_change)

        # Numerazione → re-render + preview nomi
        for var in (self.num_frames_var, self.num_angles_var, self.order_var):
            var.trace_add('write', lambda *a: self._render_canvas())

        # Solo visivo
        for var in (self.show_grid_var, self.show_numbers_var,
                    self.start_cell_var, self.end_cell_var,
                    self.sprite_prefix_var, self.anim_prefix_var,
                    self.start_letter_var, self.start_angle_var):
            var.trace_add('write', lambda *a: self._render_canvas())

    # =================================================================
    # IMMAGINE
    # =================================================================

    def _open_image(self):
        path = filedialog.askopenfilename(
            title="Apri spritesheet",
            filetypes=[("Immagini", "*.png *.jpg *.jpeg *.gif"), ("Tutti i file", "*.*")]
        )
        if not path:
            return
        try:
            self.image = Image.open(path).convert("RGBA")
            self.image_path = Path(path)
            self.filename_lbl.config(text=self.image_path.name)
            self._update_cell_range()
            self._render_canvas()
        except Exception as e:
            messagebox.showerror("Errore", f"Impossibile aprire l'immagine:\n{e}")

    def _update_cell_range(self):
        total_grid = max(1, self._safe_int(self.grid_rows_var, 1) *
                            self._safe_int(self.grid_cols_var, 1))
        total_export = max(1, self._safe_int(self.num_frames_var, 1) *
                              self._safe_int(self.num_angles_var, 1))
        cells_used = min(total_grid, total_export)
        try:
            end = int(self.end_cell_var.get())
        except (tk.TclError, ValueError):
            end = None
        if self._prev_total_cells is None or end == self._prev_total_cells:
            try:
                self.end_cell_var.set(cells_used)
            except tk.TclError:
                pass
        self._prev_total_cells = cells_used

    def _on_grid_change(self, *args):
        self._update_cell_range()
        self._render_canvas()

    def _get_canvas_viewport(self):
        self.canvas.update_idletasks()
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        return (w if w > 10 else 800, h if h > 10 else 500)

    def _compute_scale(self):
        if not self.image:
            return 1.0
        if self.zoom_var.get() == "Fit":
            vw, vh = self._get_canvas_viewport()
            return max(0.05, min((vw - 20) / self.image.width,
                                 (vh - 20) / self.image.height))
        try:
            idx = self.ZOOM_LABELS.index(self.zoom_var.get())
            return self.ZOOM_LEVELS[idx]
        except ValueError:
            return 1.0

    # =================================================================
    # CELLE
    # =================================================================

    def _compute_cell_rects(self):
        """Coordinate (x0, y0, x1, y1) in pixel immagine per ogni cella della griglia visiva."""
        if not self.image:
            return []
        rows = max(1, self._safe_int(self.grid_rows_var, 1))
        cols = max(1, self._safe_int(self.grid_cols_var, 1))
        off_x = self._safe_int(self.off_x_var, 0)
        off_y = self._safe_int(self.off_y_var, 0)
        pad_x = self._safe_int(self.pad_x_var, 0)
        pad_y = self._safe_int(self.pad_y_var, 0)
        img_w, img_h = self.image.size

        usable_w = img_w - 2 * off_x - (cols - 1) * pad_x
        usable_h = img_h - 2 * off_y - (rows - 1) * pad_y
        if usable_w <= 0 or usable_h <= 0:
            return []

        cell_w = usable_w / cols
        cell_h = usable_h / rows

        rects = []
        for r in range(rows):
            for c in range(cols):
                x0 = off_x + c * (cell_w + pad_x)
                y0 = off_y + r * (cell_h + pad_y)
                rects.append((x0, y0, x0 + cell_w, y0 + cell_h))
        return rects

    def _cell_to_label(self, cell_index):
        """Ritorna (letter, angle) della cella, o None se fuori dal range di esportazione.

        La numerazione è RELATIVA a 'Da cella': se Da cella=21, allora la cella 21
        è A1, la 22 è B1, ecc.
        """
        nf = max(1, self._safe_int(self.num_frames_var, 1))
        na = max(1, self._safe_int(self.num_angles_var, 1))
        start_cell = max(1, self._safe_int(self.start_cell_var, 1))
        relative_index = cell_index - (start_cell - 1)
        if relative_index < 0 or relative_index >= nf * na:
            return None

        if self.order_var.get() == self.ORDER_ANGLE_FRAME:
            frame_idx = relative_index // na
            angle_idx = relative_index % na
        else:
            frame_idx = relative_index % nf
            angle_idx = relative_index // nf

        sl = (self._safe_str(self.start_letter_var, "A").strip().upper() or "A")
        sa = self._safe_int(self.start_angle_var, 1)
        return chr(ord(sl) + frame_idx), sa + angle_idx

    # =================================================================
    # RENDER
    # =================================================================

    def _render_canvas(self):
        self.canvas.delete('all')
        if not self.image:
            self.info_var.set("Nessuna immagine caricata")
            return

        self.current_scale = self._compute_scale()
        img_w, img_h = self.image.size
        disp_w = int(img_w * self.current_scale)
        disp_h = int(img_h * self.current_scale)

        if self.current_scale == 1.0:
            self.tk_image = ImageTk.PhotoImage(self.image)
        else:
            resized = self.image.resize((disp_w, disp_h), Image.NEAREST)
            self.tk_image = ImageTk.PhotoImage(resized)

        self.canvas.create_image(0, 0, anchor='nw', image=self.tk_image)
        self.canvas.config(scrollregion=(0, 0, disp_w, disp_h))

        if self.show_grid_var.get():
            self._draw_grid_overlay()

        first, last = self._preview_first_last_name()
        self.info_var.set(
            f"{img_w}×{img_h}px  |  zoom {int(self.current_scale * 100)}%  |  {first} … {last}"
        )

    def _draw_grid_overlay(self):
        rects = self._compute_cell_rects()
        if not rects:
            return

        total = len(rects)
        sc = max(1, min(self._safe_int(self.start_cell_var, 1), total))
        ec = max(sc, min(self._safe_int(self.end_cell_var, total), total))
        s = self.current_scale

        # Ombra fuori range
        for i, (x0, y0, x1, y1) in enumerate(rects):
            if i + 1 < sc or i + 1 > ec:
                self.canvas.create_rectangle(x0 * s, y0 * s, x1 * s, y1 * s,
                                             fill='#000000', stipple='gray25', outline='')

        # Bordi
        for i, (x0, y0, x1, y1) in enumerate(rects):
            in_range = sc <= i + 1 <= ec
            color = '#00ff00' if in_range else '#ff3333'
            width = 2 if in_range else 1
            self.canvas.create_rectangle(x0 * s, y0 * s, x1 * s, y1 * s,
                                         outline=color, width=width)

        # Etichette
        if self.show_numbers_var.get():
            for i, (x0, y0, x1, y1) in enumerate(rects):
                cw = (x1 - x0) * s
                ch = (y1 - y0) * s
                if cw < 20 or ch < 16:
                    continue
                info = self._cell_to_label(i)
                if info is None:
                    continue
                letter, angle = info
                label = f"{letter}{angle}"

                cx = (x0 + x1) / 2 * s
                cy = (y0 + y1) / 2 * s
                in_range = sc <= i + 1 <= ec
                fill = '#ffffff' if in_range else '#999999'

                self.canvas.create_rectangle(cx - 11, cy - 8, cx + 11, cy + 8,
                                             fill='#000000', outline='', stipple='gray50')
                self.canvas.create_text(cx, cy, text=label, fill=fill,
                                        font=('Segoe UI', 10, 'bold'))

    def _preview_first_last_name(self):
        nf = max(1, self._safe_int(self.num_frames_var, 1))
        na = max(1, self._safe_int(self.num_angles_var, 1))
        sp = self._safe_str(self.sprite_prefix_var).strip().upper() or "AB"
        ap = self._safe_str(self.anim_prefix_var).strip().upper() or "CD"
        sl = self._safe_str(self.start_letter_var, "A").strip().upper() or "A"
        sa = self._safe_int(self.start_angle_var, 1)

        last_letter = chr(ord(sl) + nf - 1)
        last_angle = sa + na - 1
        return (f"{sp}{ap}{sl}{sa}", f"{sp}{ap}{last_letter}{last_angle}")

    # =================================================================
    # ZOOM
    # =================================================================

    def _zoom_in(self):
        if self.zoom_var.get() == "Fit":
            self.zoom_var.set(self.ZOOM_LABELS[3])
        else:
            try:
                idx = self.ZOOM_LABELS.index(self.zoom_var.get())
                if idx < len(self.ZOOM_LABELS) - 1:
                    self.zoom_var.set(self.ZOOM_LABELS[idx + 1])
            except ValueError:
                pass
        self._render_canvas()

    def _zoom_out(self):
        if self.zoom_var.get() == "Fit":
            return
        try:
            idx = self.ZOOM_LABELS.index(self.zoom_var.get())
            self.zoom_var.set(self.ZOOM_LABELS[idx - 1] if idx > 0 else "Fit")
        except ValueError:
            pass
        self._render_canvas()

    # =================================================================
    # RESET
    # =================================================================

    def _reset_grid(self):
        self.grid_rows_var.set(1)
        self.grid_cols_var.set(1)
        self.off_x_var.set(0)
        self.off_y_var.set(0)
        self.pad_x_var.set(0)
        self.pad_y_var.set(0)
        self.show_grid_var.set(True)
        self.show_numbers_var.set(True)
        self.num_frames_var.set(1)
        self.num_angles_var.set(1)
        self.order_var.set(self.ORDER_ANGLE_FRAME)
        self.start_letter_var.set("A")
        self.start_angle_var.set(1)
        self._prev_total_cells = None
        self._update_cell_range()
        self._render_canvas()

    # =================================================================
    # ESPORTAZIONE
    # =================================================================

    def _browse_dest(self):
        path = filedialog.askdirectory(title="Seleziona la cartella di destinazione")
        if path:
            self.dest_var.set(path)

    def _export_frames(self):
        if not self.image:
            messagebox.showwarning("Attenzione", "Apri prima uno spritesheet.")
            return

        dest_str = self._safe_str(self.dest_var).strip()
        if not dest_str or not Path(dest_str).is_dir():
            messagebox.showwarning("Attenzione", "Seleziona una cartella di destinazione valida.")
            return
        dest = Path(dest_str)

        sprite_prefix = self._safe_str(self.sprite_prefix_var).strip().upper() or "AB"
        anim_prefix = self._safe_str(self.anim_prefix_var).strip().upper() or "CD"
        if len(sprite_prefix) != 2 or len(anim_prefix) != 2:
            messagebox.showwarning("Attenzione",
                                   "I prefissi Sprite e Animazione devono essere di 2 caratteri.")
            return

        start_letter = self._safe_str(self.start_letter_var, "A").strip().upper() or "A"
        if len(start_letter) != 1 or not start_letter.isalpha():
            messagebox.showwarning("Attenzione", "La lettera iniziale deve essere A-Z.")
            return

        start_angle = self._safe_int(self.start_angle_var, 1)
        if start_angle < 0 or start_angle > 8:
            messagebox.showwarning("Attenzione", "L'angolo iniziale deve essere tra 0 e 8.")
            return

        nf = max(1, self._safe_int(self.num_frames_var, 1))
        na = max(1, self._safe_int(self.num_angles_var, 1))
        if nf > 26:
            messagebox.showwarning("Attenzione", "Massimo 26 frame (una lettera per A-Z).")
            return

        max_angle = start_angle + (na - 1)
        if max_angle > 8:
            if not messagebox.askyesno(
                "Attenzione",
                f"Stai producendo angoli fino a {max_angle}, oltre il massimo Doom (8).\n\n"
                f"Continuare comunque?"
            ):
                return

        rects = self._compute_cell_rects()
        if not rects:
            messagebox.showwarning("Attenzione",
                                   "La griglia non è valida (offset/padding troppo grandi).")
            return

        total = len(rects)
        sc = max(1, min(self._safe_int(self.start_cell_var, 1), total))
        ec = max(sc, min(self._safe_int(self.end_cell_var, total), total))

        files_info = []   # (letter, angle, cell_index, filepath)
        existing = []

        for i in range(total):
            cell_num = i + 1
            if cell_num < sc or cell_num > ec:
                continue
            info = self._cell_to_label(i)
            if info is None:
                continue
            letter, angle = info
            filename = f"{sprite_prefix}{anim_prefix}{letter}{angle}.png"
            filepath = dest / filename
            files_info.append((letter, angle, i, filepath))
            if filepath.exists():
                existing.append(filename)

        if not files_info:
            messagebox.showwarning("Attenzione", "Nessuna cella valida da esportare.")
            return

        if existing:
            preview = "\n".join(existing[:5])
            if len(existing) > 5:
                preview += f"\n… e altri {len(existing) - 5}"
            if not messagebox.askyesno(
                "File esistenti",
                f"{len(existing)} file esistono già nella destinazione:\n\n{preview}\n\n"
                f"Sovrascrivere?"
            ):
                return

        img_w, img_h = self.image.size
        exported = 0
        for letter, angle, cell_index, filepath in files_info:
            x0, y0, x1, y1 = rects[cell_index]
            cx0 = max(0, int(round(x0)))
            cy0 = max(0, int(round(y0)))
            cx1 = min(img_w, int(round(x1)))
            cy1 = min(img_h, int(round(y1)))
            if cx1 <= cx0 or cy1 <= cy0:
                continue
            crop = self.image.crop((cx0, cy0, cx1, cy1))
            try:
                crop.save(filepath, "PNG")
                exported += 1
            except Exception as e:
                messagebox.showerror("Errore", f"Impossibile salvare {filepath.name}:\n{e}")
                return

        if self.import_var.get():
            ok = self._import_to_project(files_info, dest)
            if not ok:
                messagebox.showinfo(
                    "Esportazione completata",
                    f"Esportati {exported} frame in:\n{dest}\n\n"
                    f"Import annullato (conflitto o scelta utente)."
                )
                return

        messagebox.showinfo("Fatto", f"Esportati {exported} frame in:\n{dest}")

    # =================================================================
    # IMPORT NEL PROGETTO
    # =================================================================

    def _import_to_project(self, files_info, dest_dir):
        sprite_code = self._safe_str(self.sprite_prefix_var).strip().upper() or "AB"
        anim_code = self._safe_str(self.anim_prefix_var).strip().upper() or "CD"

        profile = None
        for p in self.project.profiles:
            if p.code == sprite_code:
                profile = p
                break

        is_new_profile = False
        if not profile:
            profile = ProfileData(
                name=f"Sprite {sprite_code}",
                code=sprite_code,
                animations=[],
                folder_path=str(dest_dir)
            )
            self.project.profiles.append(profile)
            is_new_profile = True

        existing_anim = None
        for a in profile.animations:
            if a.code == anim_code:
                existing_anim = a
                break

        if existing_anim:
            answer = messagebox.askyesno(
                "Conflitto",
                f"Esiste già un'animazione con codice '{anim_code}' nel profilo "
                f"'{sprite_code}'.\n\nSovrascrivere?"
            )
            if not answer:
                if is_new_profile:
                    self.project.profiles.remove(profile)
                return False
            profile.animations.remove(existing_anim)

        anim = AnimationData(name=f"Animazione {anim_code}", code=anim_code, frames=[])

        by_letter = {}
        for letter, angle, cell_index, filepath in files_info:
            try:
                rel = str(Path(filepath).relative_to(self.project.root_path))
            except ValueError:
                rel = str(filepath)
            by_letter.setdefault(letter, []).append((angle, rel))

        for letter in sorted(by_letter.keys()):
            fg = FrameGroup(letter=letter, angles=[])
            for angle, rel in sorted(by_letter[letter], key=lambda x: x[0]):
                fg.angles.append(AngleData(
                    angle=angle,
                    file=rel,
                    duration_ms=DEFAULT_DURATION_MS,
                    mirrored=False
                ))
            anim.frames.append(fg)

        profile.animations.append(anim)

        if not profile.folder_path:
            profile.folder_path = str(dest_dir)

        pm = ProjectManager()
        pm.current_project = self.project
        pm._save_project()

        if self.on_import:
            self.on_import(profile)

        return True