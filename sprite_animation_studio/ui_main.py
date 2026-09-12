# sprite_studio/ui_main.py
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from pathlib import Path
from PIL import Image, ImageTk
import math
import time

from .constants import APP_NAME, APP_VERSION, DEFAULT_DURATION_MS, PROJECT_EXTENSION, IMG_EXTENSIONS
from .models import AnimationData, FrameGroup, AngleData, ProfileData
from .timeline import TimelineModel
from .project_manager import ProjectManager

from .ui_profile import CreateProfileDialog
from .ui_welcome import WelcomeScreen
from .settings import Settings

class ToolTip:
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
        if self.tip:
            return

        # Crea prima il tooltip, così posso misurarne le dimensioni reali
        self.tip = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.configure(bg='#333333')
        tk.Label(tw, text=self.text, justify='left',
                 bg='#333333', fg='#ffffff',
                 font=('Segoe UI', 9),
                 padx=6, pady=3).pack()

        # Forza il layout così winfo_reqwidth/height sono validi
        tw.update_idletasks()

        wx = self.widget.winfo_rootx()
        wy = self.widget.winfo_rooty()
        ww = self.widget.winfo_width()
        wh = self.widget.winfo_height()

        tw_w = tw.winfo_reqwidth()
        tw_h = tw.winfo_reqheight()

        screen_w = tw.winfo_screenwidth()
        screen_h = tw.winfo_screenheight()

        # Default: sotto il widget, allineato a sinistra
        x = wx
        y = wy + wh + 4

        # Se sborda sotto → mettilo sopra
        if y + tw_h > screen_h:
            y = wy - tw_h - 4

        # Se sborda a destra → spostalo a sinistra
        if x + tw_w > screen_w:
            x = screen_w - tw_w - 4

        # Clamp di sicurezza ai bordi
        if x < 4:
            x = 4
        if y < 4:
            y = 4

        tw.wm_geometry(f"+{x}+{y}")

    def _hide(self, event=None):
        self._cancel()
        if self.tip:
            self.tip.destroy()
            self.tip = None

class MainWindow:
    VIEWER_ZOOM_LEVELS = [0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0]
    VIEWER_ZOOM_LABELS = ["25%", "50%", "75%", "100%", "150%", "200%",
                          "300%", "400%", "600%", "800%"]

    def __init__(self, parent, project):
        self.parent = parent
        self.project = project
        self.root = parent
        self.tree_item_map = {}
        self._closed = False

        for child in parent.winfo_children():
            child.destroy()

        # Timeline
        self.timeline = TimelineModel()
        self.current_frame_idx = 0
        self.is_playing = False
        self._after_id = None
        self.selected_thumb_index = -1
        self.drag_start_index = None

        # Variabili UI
        self.code_var = tk.StringVar()
        self.folder_var = tk.StringVar(value=str(Path.cwd()))
        self.manual_files = []
        self.loop_var = tk.BooleanVar(value=True)
        self.anchor_var = tk.StringVar(value="bottom")
        self.speed_var = tk.IntVar(value=DEFAULT_DURATION_MS)
        self.viewer_zoom_var = tk.StringVar(value="Fit")
        self.settings = Settings()

        self.resources_path = None
                # Stato salvataggio
        # Stato salvataggio
        self._last_save_time = time.time()   # all'apertura il progetto è già su disco
        self._autosave_next_at = None
        self._status_tick_id = None
        self._autosave_interval = 120
        self._after_autosave = None
        self._autosave_warned = False
        self._autosave_warn_until = 0
        # Spritesheet
        #self.resources_path = None
        #self.spritesheet_files = []
        #self.current_spritesheet_index = -1
        #self.spritesheet_image = None
        #self.sheet_rows_var = tk.IntVar(value=1)
        #self.sheet_cols_var = tk.IntVar(value=1)

        # Main frame
        self.main_frame = tk.Frame(parent, bg='#2b2b2b')
        self.main_frame.pack(fill='both', expand=True)

        self._build_menu()
        self._build_content()
        parent.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        self.parent.quit()

    def _build_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Salva progetto", command=self._save_project)
        file_menu.add_command(label="Salva con nome...", command=self._save_as)
        file_menu.add_separator()
        file_menu.add_command(label="Impostazioni…", command=self._open_settings)
        file_menu.add_separator()
        file_menu.add_command(label="Chiudi progetto", command=self._close_project)
        menubar.add_cascade(label="File", menu=file_menu)
        
        tools_menu = tk.Menu(menubar, tearoff=0)

        sheet_menu = tk.Menu(tools_menu, tearoff=0)
        sheet_menu.add_command(label="Importa spritesheet…",
                               command=self._open_spritesheet_tool)
        sheet_menu.add_command(label="Esporta spritesheet…", state='disabled')
        tools_menu.add_cascade(label="Spritesheet", menu=sheet_menu)

        tools_menu.add_separator()
        tools_menu.add_command(label="Esporta… (prossimamente)", state='disabled')

        menubar.add_cascade(label="Strumenti", menu=tools_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Informazioni", command=self._show_about)
        menubar.add_cascade(label="Aiuto", menu=help_menu)

    def _open_settings(self):
        from .ui_settings import SettingsWindow
        SettingsWindow(self.root)

    def _get_angle_description(self, angle: int) -> str:
        descriptions = {
            1: "frontale",
            2: "frontale sinistro",
            3: "laterale sinistro",
            4: "posteriore sinistro",
            5: "posteriore",
            6: "posteriore destro",
            7: "laterale destro",
            8: "frontale destro"
        }
        return descriptions.get(angle, f"angolo {angle}")

    def _close_project(self):
        
        if self._closed:
            return
        self._closed = True
        ...
        if self.is_playing:
            self._pause()

        # Cancella eventuale autosave pendente
        if getattr(self, '_status_tick_id', None):
            try:
                self.root.after_cancel(self._status_tick_id)
            except Exception:
                pass
            self._status_tick_id = None
        # Rimuove le scorciatoie attaccate alla root
        for combo in self.settings.get("shortcuts").values():
            if combo:
                try:
                    self.root.unbind_all(combo)
                except tk.TclError:
                    pass
 
        self.timeline.clear()

        if hasattr(self, '_tk_img'):
            self._tk_img = None
        if hasattr(self, '_bg_image'):
            self._bg_image = None
        
        self.thumb_refs.clear()
        self.tree.delete(*self.tree.get_children())
        self.main_frame.destroy()

        def on_project_loaded(project):
            from .ui_main import MainWindow
            MainWindow(self.root, project)
            self.root.title(f"{APP_NAME} v{APP_VERSION} - {project.name}")

        WelcomeScreen(self.root, on_project_loaded)

    # -----------------------------------------------------------------
    # BUILD CONTENT
    # -----------------------------------------------------------------

    def _build_content(self):
        main_pane = ttk.PanedWindow(self.main_frame, orient='horizontal')
        main_pane.pack(fill='both', expand=True)

        # ---- Pannello sinistro ----
        left_frame = ttk.Frame(main_pane, width=280)
        main_pane.add(left_frame, weight=0)
        left_frame.pack_propagate(False)

        # ---- RISORSE ----
        resources_frame = ttk.LabelFrame(left_frame, text="Risorse", padding=3)
        resources_frame.pack(fill='x', padx=3, pady=3)

        path_row = ttk.Frame(resources_frame)
        path_row.pack(fill='x', pady=2)
        self.resources_path_var = tk.StringVar(value="Nessuna cartella selezionata")
        self.resources_path_lbl = ttk.Label(path_row, textvariable=self.resources_path_var,
                                            foreground='#888888', font=('Segoe UI', 8))
        self.resources_path_lbl.pack(side='left', fill='x', expand=True)
        ttk.Button(resources_frame, text="📁", width=3,
                   command=self._select_resources_folder).pack(side='right', padx=2)

        self.resources_listbox = tk.Listbox(resources_frame, bg='#3a3a3a', fg='#cccccc',
                                            font=('Segoe UI', 8), height=6, relief='flat')
        self.resources_listbox.pack(fill='x', pady=2)

        self.btn_library_action = ttk.Button(resources_frame, text="📚 Crea libreria",
                                             command=self._create_library_from_resources)
        self.btn_library_action.pack(fill='x', pady=2)

        # ---- LIBRERIE ----
        libs_frame = ttk.LabelFrame(left_frame, text="Librerie", padding=3)
        libs_frame.pack(fill='both', expand=True, padx=3, pady=3)

        self.tree = ttk.Treeview(libs_frame, columns=('type',), show='tree', height=10)
        self.tree.pack(fill='both', expand=True, padx=2, pady=2)
        self.tree.bind('<<TreeviewSelect>>', self._on_tree_select)
        self.tree.bind('<Button-1>', self._on_tree_click)

        btn_frame = ttk.Frame(libs_frame)
        btn_frame.pack(fill='x', padx=2, pady=2)
        btn_frame = ttk.Frame(libs_frame)
        btn_frame.pack(fill='x', padx=2, pady=2)

        b1 = ttk.Button(btn_frame, text="📚", width=4, command=self._create_first_profile)
        b1.pack(side='left', padx=2)
        ToolTip(b1, "Nuova libreria")

        b2 = ttk.Button(btn_frame, text="🎞️", width=4, command=self._new_animation)
        b2.pack(side='left', padx=2)
        ToolTip(b2, "Nuova animazione")

        b3 = ttk.Button(btn_frame, text="🗑️", width=4, command=self._delete_selected_item)
        b3.pack(side='left', padx=2)
        ToolTip(b3, "Elimina selezionato")

        # ---- Pannello centrale ----
        center_frame = ttk.Frame(main_pane)
        main_pane.add(center_frame, weight=1)

        viewer_frame = ttk.Frame(center_frame)
        viewer_frame.pack(fill='both', expand=True, padx=0, pady=5)

        # Canvas
        # --- Barra zoom viewer ---
        zoom_bar = ttk.Frame(viewer_frame)
        zoom_bar.pack(fill='x', padx=4, pady=(2, 0))

        ttk.Button(zoom_bar, text="+", width=2,
                   command=self._viewer_zoom_in).pack(side='right', padx=(2, 4))
        ttk.Button(zoom_bar, text="−", width=2,
                   command=self._viewer_zoom_out).pack(side='right')

        self.viewer_zoom_combo = ttk.Combobox(
            zoom_bar, textvariable=self.viewer_zoom_var, state='readonly',
            values=["Fit"] + self.VIEWER_ZOOM_LABELS, width=6
        )
        self.viewer_zoom_combo.pack(side='right', padx=(0, 2))
        self.viewer_zoom_combo.bind('<<ComboboxSelected>>',
                                    lambda e: self._update_display())

        ttk.Label(zoom_bar, text="Zoom:").pack(side='right', padx=(0, 3))
        canvas_container = ttk.Frame(viewer_frame)
        canvas_container.pack(fill='both', expand=True)
        self.canvas = tk.Canvas(canvas_container, bg='#222222', highlightthickness=1,
                                highlightbackground='#444444')
        self.canvas.pack(fill='both', expand=True)

        # ---- Controlli angolo ----
        angle_controls = ttk.Frame(viewer_frame)
        angle_controls.pack(pady=5, anchor='center') 

        # Freccia sinistra
        self.btn_angle_left = ttk.Button(angle_controls, text="◀", width=4, padding=(10, 20),
                                        command=self._prev_angle)
        self.btn_angle_left.pack(side='left', padx=5)        # Canvas per i pallini (selettore a cerchio)
        self.dot_canvas = tk.Canvas(angle_controls, bg='#2b2b2b', width=180, height=60,
                                    highlightthickness=0)
        self.dot_canvas.pack(side='left', padx=5)

        # Mappatura corretta: 1 in basso, 5 in alto
        # Angoli in gradi (0° = destra, 90° = basso)
        angle_positions = {
            1: 270,    # basso
            2: 225,   # basso-sx
            3: 180,   # sx
            4: 135,   # alto-sx
            5: 90,   # alto (o -90)
            6: 45,   # alto-dx (o -45)
            7: 0,     # dx
            8: 315     # basso-dx
        }
        center_x, center_y = 90, 30
        radius = 22

        self.dot_ids = {}

        for angle, deg in angle_positions.items():
            rad = math.radians(deg)
            x = center_x + radius * math.cos(rad)
            y = center_y - radius * math.sin(rad)  # inverti y per avere 0° a destra

            dot_id = self.dot_canvas.create_oval(x-7, y-7, x+7, y+7,
                                                fill='#555555', outline='#444444', width=1)
            self.dot_ids[angle] = dot_id
            self.dot_canvas.tag_bind(dot_id, '<Button-1>', lambda e, a=angle: self._set_angle(a))

        # Freccia destra
        self.btn_angle_right = ttk.Button(angle_controls, text="▶", width=4, padding=(10, 20),
                                            command=self._next_angle)
        self.btn_angle_right.pack(side='left', padx=5)
        # Etichetta descrizione angolo
        self.angle_label = ttk.Label(angle_controls, text="1 - frontale", foreground='#4a9eff',
                                     font=('Segoe UI', 10, 'bold'), width=25, anchor='w')
        self.angle_label.pack(side='left', padx=15)

        # ---- Info animazione ----
        info_frame = ttk.Frame(viewer_frame)
        info_frame.pack(fill='x', pady=2)
        self.info_lbl = ttk.Label(info_frame, text="", foreground='#888888', font=('Segoe UI', 9))
        self.info_lbl.pack()

        # ---- Timeline ----
        timeline_frame = ttk.LabelFrame(center_frame, text="Timeline", padding=3)
        timeline_frame.pack(fill='x', padx=5, pady=5)

        thumb_container = ttk.Frame(timeline_frame)
        thumb_container.pack(fill='x', pady=2)
        self.thumb_canvas = tk.Canvas(thumb_container, bg='#1a1a1a', height=60,
                                      highlightthickness=0)
        self.thumb_canvas.pack(fill='x', padx=2, pady=2)
        self.thumb_refs = []

        # ---- Player ----
        player_frame = ttk.Frame(timeline_frame)
        player_frame.pack(fill='x', pady=2)

        ttk.Button(player_frame, text="▶ Play", command=self._play).pack(side='left', padx=2)
        ttk.Button(player_frame, text="⏸ Pausa", command=self._pause).pack(side='left', padx=2)
        ttk.Button(player_frame, text="⏹ Stop", command=self._stop).pack(side='left', padx=2)
        ttk.Checkbutton(player_frame, text="Loop", variable=self.loop_var).pack(side='left', padx=5)

        ttk.Label(player_frame, text="Durata (ms):").pack(side='left', padx=(10, 3))
        self.speed_spin = ttk.Spinbox(player_frame, from_=20, to=2000, increment=10,
                                      width=6, textvariable=self.speed_var)
        self.speed_spin.pack(side='left')
        self.speed_spin.bind('<KeyRelease>', self._on_speed_change_debounced)
        self.speed_spin.bind('<Return>', self._on_speed_change)
        self.speed_spin.bind('<FocusOut>', self._on_speed_change)
        self.speed_spin.configure(command=self._on_speed_change)
        
        self.time_lbl = ttk.Label(player_frame, text="0s 0ms 0tick", foreground='#666')
        self.time_lbl.pack(side='right', padx=10)


        # ---- SAVE STATUS ----
        self.save_status_lbl = ttk.Label(player_frame, text="",
                                          foreground='#4a9eff',
                                          font=('Segoe UI', 8))
        self.save_status_lbl.pack(side='right', padx=10)

        # ---- Azioni ----
        action_frame = ttk.Frame(timeline_frame)
        action_frame.pack(fill='x', pady=2)

        b4 = ttk.Button(action_frame, text="⇄", width=4,
                        command=self._clone_mirror_single_frame)
        b4.pack(side='left', padx=2)
        ToolTip(b4, "Clona e specchia (singolo)")

        b5 = ttk.Button(action_frame, text="⇄⇄", width=4,
                        command=self._clone_mirror_all_frames)
        b5.pack(side='left', padx=2)
        ToolTip(b5, "Clona e specchia (tutti)")

        b6 = ttk.Button(action_frame, text="🗑️", width=4,
                        command=self._delete_current_frame)
        b6.pack(side='left', padx=2)
        ToolTip(b6, "Elimina frame corrente")

        self._refresh_tree()
        self._check_profiles()
        self._update_angle_dots()
        self._bind_shortcuts()
        self._start_autosave()


    # -----------------------------------------------------------------
    # SELEZIONE ANGOLI
    # -----------------------------------------------------------------

        
    def _update_angle_dots(self):
        if not self.dot_canvas:
            return

        # Se non ci sono frame, mostra tutti grigi
        if not self.timeline.frames:
            for dot_id in self.dot_ids.values():
                self.dot_canvas.itemconfig(dot_id, fill='#555555', outline='#444444')
            return

        current_angle = self.timeline.current_angle
        available_angles = []
        if self.current_frame_idx < len(self.timeline.frames):
            available_angles = self.timeline.get_available_angles(self.current_frame_idx)

        for angle, dot_id in self.dot_ids.items():
            if angle == current_angle:
                color = '#000000'
                outline = '#4a9eff'
            elif angle in available_angles:
                color = '#ffffff'
                outline = '#aaaaaa'
            else:
                color = '#555555'
                outline = '#444444'
            self.dot_canvas.itemconfig(dot_id, fill=color, outline=outline)

    def _set_angle(self, angle):
        if angle < 1 or angle > 8:
            return
        self.timeline.set_angle(angle)
        self.angle_label.config(text=f"{angle} - {self._get_angle_description(angle)}")
        self._update_display()
        self._update_angle_dots()

    def _prev_angle(self):
        new_angle = self.timeline.current_angle + 1
        if new_angle > 8:
            new_angle = 1
        self._set_angle(new_angle)

    def _next_angle(self):
        new_angle = self.timeline.current_angle - 1
        if new_angle < 1:
            new_angle = 8
        self._set_angle(new_angle)

    # -----------------------------------------------------------------
    # CLONA E SPECCHIA
    # -----------------------------------------------------------------
    def _create_mirrored_png(self, profile, anim, frame_letter, mirror_angle, src_file):
        """Crea il PNG specchiato nella cartella del profilo. Ritorna il percorso
        relativo al project_root o None in caso di errore."""
        src_path = Path(src_file)
        if not src_path.is_absolute():
            src_path = self.project.root_path / src_path
        if not src_path.exists():
            return None

        dest_dir = Path(profile.folder_path) if profile.folder_path else src_path.parent
        dest_dir.mkdir(parents=True, exist_ok=True)
        new_name = f"{profile.code}{anim.code}{frame_letter}{mirror_angle}.png"
        dest_path = dest_dir / new_name

        try:
            img = Image.open(src_path).convert("RGBA")
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
            img.save(dest_path, "PNG")
        except Exception as e:
            print(f"Errore creando specchio: {e}")
            return None

        try:
            return str(dest_path.relative_to(self.project.root_path))
        except ValueError:
            return str(dest_path)

    def _clone_mirror_single_frame(self):
        if not self.timeline.frames:
            messagebox.showinfo("Info", "Nessuna animazione caricata.")
            return

        current_angle = self.timeline.current_angle
        mirror_map = {2: 8, 8: 2, 3: 7, 7: 3, 4: 6, 6: 4}
        if current_angle not in mirror_map:
            messagebox.showinfo("Info", f"L'angolo {current_angle} non ha un mirror definito.")
            return
        mirror_angle = mirror_map[current_angle]

        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Seleziona un'animazione nella libreria.")
            return
        item = sel[0]
        if item not in self.tree_item_map:
            return
        p_idx, a_idx = self.tree_item_map[item]
        if a_idx < 0:
            messagebox.showinfo("Info", "Seleziona un'animazione, non un profilo.")
            return
        if p_idx < 0 or p_idx >= len(self.project.profiles):
            return
        profile = self.project.profiles[p_idx]
        if a_idx >= len(profile.animations):
            return
        anim = profile.animations[a_idx]

        current_letter = self.timeline.get_frame_letter(self.current_frame_idx)
        if not current_letter:
            return

        target_fg = None
        for fg in anim.frames:
            if fg.letter == current_letter:
                target_fg = fg
                break
        if not target_fg:
            return

        for ad in target_fg.angles:
            if ad.angle == mirror_angle:
                messagebox.showinfo("Info", f"L'angolo {mirror_angle} esiste già per il frame {current_letter}.")
                return

        src_ad = None
        for ad in target_fg.angles:
            if ad.angle == current_angle:
                src_ad = ad
                break
        if not src_ad:
            return

        new_file = self._create_mirrored_png(
            profile, anim, current_letter, mirror_angle, src_ad.file
        )
        if new_file is None:
            messagebox.showerror("Errore", "Impossibile creare il file specchiato.")
            return

        new_ad = AngleData(
            angle=mirror_angle,
            file=new_file,
            duration_ms=src_ad.duration_ms,
            mirrored=False
        )
        target_fg.angles.append(new_ad)

        pm = ProjectManager()
        pm.current_project = self.project
        pm._save_project()

        self.timeline.load_from_animation(anim, self.project.root_path)
        self._update_display()
        self._update_angle_dots()
        self.info_lbl.config(text=f"Clonato angolo {current_angle} → {mirror_angle} (singolo frame)")

    def _clone_mirror_all_frames(self):
        if not self.timeline.frames:
            messagebox.showinfo("Info", "Nessuna animazione caricata.")
            return

        current_angle = self.timeline.current_angle
        mirror_map = {2: 8, 8: 2, 3: 7, 7: 3, 4: 6, 6: 4}
        if current_angle not in mirror_map:
            messagebox.showinfo("Info", f"L'angolo {current_angle} non ha un mirror definito.")
            return
        mirror_angle = mirror_map[current_angle]

        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Seleziona un'animazione nella libreria.")
            return
        item = sel[0]
        if item not in self.tree_item_map:
            return
        p_idx, a_idx = self.tree_item_map[item]
        if a_idx < 0:
            messagebox.showinfo("Info", "Seleziona un'animazione, non un profilo.")
            return
        if p_idx < 0 or p_idx >= len(self.project.profiles):
            return
        profile = self.project.profiles[p_idx]
        if a_idx >= len(profile.animations):
            return
        anim = profile.animations[a_idx]

        cloned = 0
        for fg in anim.frames:
            has_mirror = any(ad.angle == mirror_angle for ad in fg.angles)
            if has_mirror:
                continue
            src_ad = None
            for ad in fg.angles:
                if ad.angle == current_angle:
                    src_ad = ad
                    break
            if not src_ad:
                continue
            
            new_file = self._create_mirrored_png(
                profile, anim, fg.letter, mirror_angle, src_ad.file
            )
            if new_file is None:
                continue
            new_ad = AngleData(
                angle=mirror_angle,
                file=new_file,
                duration_ms=src_ad.duration_ms,
                mirrored=False
            )
            fg.angles.append(new_ad)
            cloned += 1

        if cloned == 0:
            messagebox.showinfo("Info", f"L'angolo {mirror_angle} esiste già per tutti i frame.")
            return

        pm = ProjectManager()
        pm.current_project = self.project
        pm._save_project()

        self.timeline.load_from_animation(anim, self.project.root_path)
        self._update_display()
        self._update_angle_dots()
        self.info_lbl.config(text=f"Clonato angolo {current_angle} → {mirror_angle} su {cloned} frame")

    # -----------------------------------------------------------------
    # ELIMINA FRAME
    # -----------------------------------------------------------------

    def _delete_current_frame(self):
        if not self.timeline.frames:
            messagebox.showinfo("Info", "Nessuna animazione caricata.")
            return

        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Seleziona un'animazione nella libreria.")
            return
        item = sel[0]
        if item not in self.tree_item_map:
            return
        p_idx, a_idx = self.tree_item_map[item]
        if a_idx < 0:
            messagebox.showinfo("Info", "Seleziona un'animazione, non un profilo.")
            return
        if p_idx < 0 or p_idx >= len(self.project.profiles):
            return
        profile = self.project.profiles[p_idx]
        if a_idx >= len(profile.animations):
            return
        anim = profile.animations[a_idx]

        current_letter = self.timeline.get_frame_letter(self.current_frame_idx)
        if not current_letter:
            return

        target_idx = -1
        for idx, fg in enumerate(anim.frames):
            if fg.letter == current_letter:
                target_idx = idx
                break

        if target_idx == -1:
            messagebox.showinfo("Info", f"Frame {current_letter} non trovato.")
            return

        if not messagebox.askyesno("Conferma", f"Eliminare il frame '{current_letter}'?"):
            return

        self.timeline.delete_frame(self.current_frame_idx)
        del anim.frames[target_idx]

        pm = ProjectManager()
        pm.current_project = self.project
        pm._save_project()

        self._refresh_tree()
        self._update_display()
        self._update_angle_dots()
        self.info_lbl.config(text=f"Frame '{current_letter}' eliminato")

    # -----------------------------------------------------------------
    # METODI RISORSE E LIBRERIE
    # -----------------------------------------------------------------

    def _update_button_state(self):
        sel = self.tree.selection()
        if not sel:
            self.btn_library_action.config(text="📚 Crea libreria", command=self._create_library_from_resources)
            return
        item = sel[0]
        if item not in self.tree_item_map:
            self.btn_library_action.config(text="📚 Crea libreria", command=self._create_library_from_resources)
            return
        p_idx, a_idx = self.tree_item_map[item]
        if p_idx < 0 or p_idx >= len(self.project.profiles):
            self.btn_library_action.config(text="📚 Crea libreria", command=self._create_library_from_resources)
            return
        self.btn_library_action.config(text="📂 Aggiorna libreria", command=self._update_selected_library)

    def _create_library_from_resources(self):
        if not self.resources_path:
            messagebox.showwarning("Attenzione", "Seleziona prima una cartella in Risorse.")
            return

        def on_profile_created(profile):
            self._refresh_tree()
            self._check_profiles()
            if profile.animations:
                anim = profile.animations[0]
                self.timeline.load_from_animation(anim, self.project.root_path)
                self.current_frame_idx = 0
                self._update_display()
                self._update_angle_dots()
                self.info_lbl.config(text=f"{anim.name} ({len(self.timeline.frames)} frame)")
            else:
                self.info_lbl.config(text=f"Libreria '{profile.name}' creata (vuota)")

        dialog = CreateProfileDialog(self.root, self.project, on_profile_created)
        dialog.root_path.set(self.resources_path)
        dialog._scan_folder()

    def _update_selected_library(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Seleziona prima una libreria o un'animazione da aggiornare.")
            return

        item = sel[0]
        if item not in self.tree_item_map:
            return
        p_idx, a_idx = self.tree_item_map[item]
        if p_idx < 0 or p_idx >= len(self.project.profiles):
            return
        profile = self.project.profiles[p_idx]

        if not self.resources_path or not Path(self.resources_path).exists():
            folder = filedialog.askdirectory(title="Seleziona la cartella per la libreria")
            if not folder:
                return
            self.resources_path = folder
            self.resources_path_var.set(folder)
            self._update_resources_from_path(folder)

        root = Path(self.resources_path)
        padre = profile.code
        groups = {}
        valid_files = 0

        all_images = []
        for ext in IMG_EXTENSIONS:
            all_images.extend(root.rglob(f"*{ext}"))

        for f in all_images:
            stem = f.stem
            if len(stem) >= 6:
                code_full = stem[:4]
                file_padre = code_full[:2]
                figlio = code_full[2:4]
                if file_padre == padre:
                    rest = stem[4:]
                    if len(rest) >= 2 and rest[0].isalpha() and rest[1].isdigit():
                        letter = rest[0]
                        angle_str = rest[1]
                        angle = int(angle_str)
                        if angle == 0:
                            angle = 1
                        if figlio not in groups:
                            groups[figlio] = {}
                        if letter not in groups[figlio]:
                            groups[figlio][letter] = {}
                        if angle not in groups[figlio][letter]:
                            groups[figlio][letter][angle] = []
                        groups[figlio][letter][angle].append(f)
                        valid_files += 1

                        if len(stem) >= 8:
                            mirror_letter = stem[6]
                            mirror_angle_str = stem[7]
                            if mirror_letter.isalpha() and mirror_angle_str.isdigit():
                                mirror_angle = int(mirror_angle_str)
                                if (angle == 2 and mirror_angle == 8) or \
                                   (angle == 8 and mirror_angle == 2) or \
                                   (angle == 3 and mirror_angle == 7) or \
                                   (angle == 7 and mirror_angle == 3) or \
                                   (angle == 4 and mirror_angle == 6) or \
                                   (angle == 6 and mirror_angle == 4):
                                    if mirror_angle not in groups[figlio][letter]:
                                        groups[figlio][letter][mirror_angle] = []
                                    if f not in groups[figlio][letter][mirror_angle]:
                                        groups[figlio][letter][mirror_angle].append(f)
                                        valid_files += 1

        if a_idx == -1:
            profile.animations.clear()
            for figlio, letters in sorted(groups.items()):
                anim = AnimationData(name=f"Animazione {figlio}", code=figlio, frames=[])
                for letter, angles in sorted(letters.items()):
                    frame_group = FrameGroup(letter=letter, angles=[])
                    for angle, files in sorted(angles.items()):
                        if files:
                            f = files[0]
                            try:
                                rel_path = str(f.relative_to(self.project.root_path))
                            except ValueError:
                                rel_path = str(f)
                            mirrored = False
                            stem = f.stem
                            if len(stem) >= 8:
                                mirror_letter = stem[6]
                                mirror_angle_str = stem[7]
                                if mirror_letter.isalpha() and mirror_angle_str.isdigit():
                                    mirror_angle = int(mirror_angle_str)
                                    if angle == mirror_angle:
                                        mirrored = True
                            frame_group.angles.append(AngleData(
                                angle=angle,
                                file=rel_path,
                                duration_ms=DEFAULT_DURATION_MS,
                                mirrored=mirrored
                            ))
                    anim.frames.append(frame_group)
                profile.animations.append(anim)
            self.info_lbl.config(text=f"Libreria '{profile.name}' aggiornata ({len(profile.animations)} animazioni)")

        else:
            if a_idx >= len(profile.animations):
                return
            anim = profile.animations[a_idx]
            anim_code = anim.code

            new_anim = AnimationData(name=anim.name, code=anim_code, frames=[])
            for letter, angles in sorted(groups.get(anim_code, {}).items()):
                frame_group = FrameGroup(letter=letter, angles=[])
                for angle, files in sorted(angles.items()):
                    if files:
                        f = files[0]
                        try:
                            rel_path = str(f.relative_to(self.project.root_path))
                        except ValueError:
                            rel_path = str(f)
                        mirrored = False
                        stem = f.stem
                        if len(stem) >= 8:
                            mirror_letter = stem[6]
                            mirror_angle_str = stem[7]
                            if mirror_letter.isalpha() and mirror_angle_str.isdigit():
                                mirror_angle = int(mirror_angle_str)
                                if angle == mirror_angle:
                                    mirrored = True
                        frame_group.angles.append(AngleData(
                            angle=angle,
                            file=rel_path,
                            duration_ms=DEFAULT_DURATION_MS,
                            mirrored=mirrored
                        ))
                new_anim.frames.append(frame_group)

            profile.animations[a_idx] = new_anim
            self.info_lbl.config(text=f"Animazione '{anim.name}' aggiornata ({len(new_anim.frames)} frame)")

        pm = ProjectManager()
        pm.current_project = self.project
        pm._save_project()

        self._refresh_tree()
        self._check_profiles()
        self._update_resources_from_path(profile.folder_path)

    def _update_resources_from_path(self, path, filter_prefix=None):
        if not path or not Path(path).exists():
            self.resources_path_var.set("Cartella non trovata")
            self.resources_listbox.delete(0, tk.END)
            return

        self.resources_path = path
        self.resources_path_var.set(path)
        self.resources_listbox.delete(0, tk.END)

        folder = Path(path)
        items = sorted(folder.iterdir(), key=lambda x: (not x.is_file(), x.name.lower()))
        for item in items:
            if item.is_file():
                name = item.name
                if filter_prefix and not name.startswith(filter_prefix):
                    continue
                self.resources_listbox.insert(tk.END, f"📄 {name}")
            else:
                self.resources_listbox.insert(tk.END, f"📁 {item.name}/")

    def _select_resources_folder(self):
        sel = self.tree.selection()
        if sel:
            item = sel[0]
            if item in self.tree_item_map:
                p_idx, a_idx = self.tree_item_map[item]
                if p_idx >= 0 and p_idx < len(self.project.profiles):
                    profile = self.project.profiles[p_idx]
                    if a_idx == -1:
                        folder = filedialog.askdirectory(
                            title=f"Seleziona la nuova cartella per '{profile.name}'",
                            initialdir=profile.folder_path if profile.folder_path else None
                        )
                        if folder:
                            profile.folder_path = folder
                            self.resources_path = folder
                            self.resources_path_var.set(folder)
                            self._update_resources_from_path(folder)
                            pm = ProjectManager()
                            pm.current_project = self.project
                            pm._save_project()
                        return

        path = filedialog.askdirectory(title="Seleziona la cartella risorse")
        if path:
            self.resources_path = path
            self.resources_path_var.set(path)
            self._update_resources_from_path(path)

    # -----------------------------------------------------------------
    # SPRITESHEET METODI
    # -----------------------------------------------------------------

    
    # -----------------------------------------------------------------
    # METODI TIMELINE E PLAYER
    # -----------------------------------------------------------------

    def _check_profiles(self):
        if not self.project.profiles:
            self._show_empty_overlay()
        else:
            self._hide_empty_overlay()

    def _show_empty_overlay(self):
        if hasattr(self, 'empty_overlay') and self.empty_overlay:
            return
        self.empty_overlay = tk.Frame(self.main_frame, bg='#000000', bd=0)
        self.empty_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        dark_bg = tk.Frame(self.empty_overlay, bg='#000000')
        dark_bg.place(relx=0, rely=0, relwidth=1, relheight=1)
        center = tk.Frame(self.empty_overlay, bg='#2b2b2b')
        center.place(relx=0.5, rely=0.5, anchor='center')
        plus_btn = tk.Button(center, text="+", font=('Segoe UI', 60, 'bold'),
                             bg='#4a9eff', fg='white', relief='flat',
                             width=3, height=1, command=self._create_first_profile)
        plus_btn.pack(pady=10)
        label = tk.Label(center, text="Crea la tua prima libreria", font=('Segoe UI', 14),
                         bg='#2b2b2b', fg='#ffffff')
        label.pack()
        self._set_controls_state('disabled')

    def _hide_empty_overlay(self):
        if hasattr(self, 'empty_overlay') and self.empty_overlay:
            self.empty_overlay.destroy()
            self.empty_overlay = None
        self._set_controls_state('normal')

    def _bind_shortcuts(self):
        s = self.settings.get("shortcuts")
        # Rimuove eventuali bind precedenti
        for combo in s.values():
            if combo:                      # ← fondamentale: se è stringa vuota, unbind_all("") cancella TUTTO
                try:
                    self.root.unbind_all(combo)
                except tk.TclError:
                    pass

        mapping = {
            "save":       self._save_project,
            "save_as":    self._save_as,
            "open":       lambda: self._close_project(),
            "new":        lambda: self._close_project(),
            "play":       self._play,
            "pause":      self._pause,
            "stop":       self._stop,
            "next_frame": lambda: self._step_frame(+1),
            "prev_frame": lambda: self._step_frame(-1),
            "next_angle": self._next_angle,
            "prev_angle": self._prev_angle,
        }
        for action, combo in s.items():
            if action in mapping and combo:
                try:
                    self.root.bind_all(combo, lambda e, f=mapping[action]: f())
                except tk.TclError:
                    pass

    def _step_frame(self, delta):
        if not self.timeline.frames:
            return
        n = len(self.timeline.frames)
        self.current_frame_idx = (self.current_frame_idx + delta) % n
        self._update_display()

    def _start_autosave(self):
         # Avvia sempre il tick dell'etichetta (serve anche per "salvato")
        self._update_save_status_tick()
        if not self.settings.get("editor", "autosave_enabled", False):
            return
        self._autosave_interval = int(self.settings.get("editor", "autosave_interval_sec", 120))
        self._autosave_next_at = time.time() + self._autosave_interval
        self._after_autosave = self.root.after(self._autosave_interval * 1000,
                                                self._autosave_tick)
    
    def _autosave_tick(self):
        try:
            self._save_project()
        except Exception as e:
            print(f"Autosave error: {e}")
        interval = int(self.settings.get("editor", "autosave_interval_sec", 120))
        self._after_autosave = self.root.after(interval * 1000, self._autosave_tick)


    def _update_save_status_tick(self):
        if not hasattr(self, 'save_status_lbl'):
            return
        now = time.time()
        text = ""

        # Priorità 1: "salvato" per 3 secondi dopo un salvataggio
        if (now - self._last_save_time) < 3:
            text = "💾 salvato"
        # Priorità 2: countdown 10s prima dell'autosave, visibile per 3s
        elif self._autosave_next_at:
            remaining = self._autosave_next_at - now
            if remaining <= 10 and not self._autosave_warned:
                self._autosave_warned = True
                self._autosave_warn_until = now + 3
            if remaining > 10:
                self._autosave_warned = False
            if self._autosave_warn_until > now:
                text = f"auto tra {max(0, int(remaining))}s"

        try:
            self.save_status_lbl.config(text=text)
        except tk.TclError:
            return
        self._status_tick_id = self.root.after(500, self._update_save_status_tick)

    def _set_controls_state(self, state):
        if hasattr(self, 'code_entry'):
            self.code_entry.config(state=state)
        for child in self.main_frame.winfo_children():
            if isinstance(child, (ttk.Button, tk.Button)):
                try:
                    child.config(state=state)
                except:
                    pass
            elif isinstance(child, (ttk.Entry, tk.Entry)):
                try:
                    child.config(state=state)
                except:
                    pass

    def _create_first_profile(self):
        def on_profile_created(profile):
            self._refresh_tree()
            self._check_profiles()
            if profile.animations:
                anim = profile.animations[0]
                self.timeline.load_from_animation(anim, self.project.root_path)
                self.current_frame_idx = 0
                self._update_display()
                self._update_angle_dots()
                self.info_lbl.config(text=f"{anim.name} ({len(self.timeline.frames)} frame)")

        CreateProfileDialog(self.root, self.project, on_profile_created)

    def _on_tree_select(self, event):
        sel = self.tree.selection()
        if not sel:
            self._clear_timeline()
            self._clear_resources()
            self._update_button_state()
            self._update_angle_dots()
            return

        item = sel[0]
        if item not in self.tree_item_map:
            return
        p_idx, a_idx = self.tree_item_map[item]
        if p_idx < 0 or p_idx >= len(self.project.profiles):
            return

        profile = self.project.profiles[p_idx]
        self._update_button_state()

        if a_idx == -1:
            if profile.folder_path and Path(profile.folder_path).exists():
                filter_prefix = profile.code
                self._update_resources_from_path(profile.folder_path, filter_prefix)
                self.resources_path_var.set(profile.folder_path)
            else:
                self.resources_path_var.set("Nessuna cartella associata (clicca su 'Aggiorna libreria')")
                self.resources_listbox.delete(0, tk.END)
                self._clear_timeline()
            return

        if a_idx >= len(profile.animations):
            return

        anim = profile.animations[a_idx]

        if profile.folder_path and Path(profile.folder_path).exists():
            filter_prefix = profile.code + anim.code
            self._update_resources_from_path(profile.folder_path, filter_prefix)
        else:
            self.resources_path_var.set("Nessuna cartella associata")
            self.resources_listbox.delete(0, tk.END)

        # Carica l'animazione
        self.timeline.load_from_animation(anim, self.project.root_path)
        self.current_frame_idx = 0


        # Imposta l'angolo di default
        if self.timeline.frames:
            available = self.timeline.get_available_angles(0)
            if available:
                default_angle = 1 if 1 in available else available[0]
            else:
                default_angle = 1
            self._set_angle(default_angle)
        else:
            self._update_angle_dots()

        self.info_lbl.config(text=f"{anim.name} ({len(self.timeline.frames)} frame)")

    def _on_tree_click(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            self.tree.selection_remove(*self.tree.selection())
            self._clear_resources()
            self._clear_timeline()
            self._update_button_state()
            self._update_angle_dots()

    def _clear_resources(self):
        self.resources_path = None
        self.resources_path_var.set("Nessuna libreria selezionata")
        self.resources_listbox.delete(0, tk.END)

    def _clear_timeline(self):
        self.timeline.clear()
        self.current_frame_idx = 0
        self.canvas.delete('all')
        if hasattr(self, '_tk_img'):
            self._tk_img = None
        self.thumb_canvas.delete('all')
        self.thumb_refs.clear()
        self.info_lbl.config(text="")
        self.time_lbl.config(text="0s 0ms 0tick")
        self.angle_label.config(text="1 - frontale")
        # Resetta i pallini a grigi
        for dot_id in self.dot_ids.values():
            self.dot_canvas.itemconfig(dot_id, fill='#555555', outline='#444444')

    def _refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        self.tree_item_map = {}

        for p_idx, profile in enumerate(self.project.profiles):
            profile_id = self.tree.insert("", "end", text=f"{profile.name} [{profile.code}]")
            self.tree_item_map[profile_id] = (p_idx, -1)
            for a_idx, anim in enumerate(profile.animations):
                anim_id = self.tree.insert(profile_id, "end", text=f"  {anim.name} [{anim.code}]")
                self.tree_item_map[anim_id] = (p_idx, a_idx)

        self._check_profiles()
        self._update_button_state()

    def _new_animation(self):
        if not self.project.profiles:
            messagebox.showwarning("Attenzione", "Crea prima un profilo.")
            return

        target_p_idx = 0
        sel = self.tree.selection()
        if sel and sel[0] in self.tree_item_map:
            p_idx, a_idx = self.tree_item_map[sel[0]]
            if 0 <= p_idx < len(self.project.profiles):
                target_p_idx = p_idx

        name = simpledialog.askstring("Nome animazione", "Inserisci il nome:")
        if not name:
            return
        code = simpledialog.askstring("Codice animazione", "Codice (2 caratteri):")
        if not code or len(code) != 2:
            messagebox.showwarning("Attenzione", "Il codice deve essere di 2 caratteri.")
            return
        code = code.upper()

        anim = AnimationData(name=name, code=code, frames=[])
        self.project.profiles[target_p_idx].animations.append(anim)
        self._refresh_tree()
        self._save_project()

    def _delete_selected_item(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Seleziona un elemento da eliminare.")
            return

        item = sel[0]
        if item not in self.tree_item_map:
            return

        p_idx, a_idx = self.tree_item_map[item]
        if p_idx < 0 or p_idx >= len(self.project.profiles):
            return
        profile = self.project.profiles[p_idx]

        if a_idx == -1:
            if messagebox.askyesno("Conferma",
                                   f"Eliminare il profilo '{profile.name}' e tutte le sue animazioni?"):
                del self.project.profiles[p_idx]
                self.timeline.clear()
                self._refresh_tree()
                self._update_display()
                self.info_lbl.config(text=f"Profilo '{profile.name}' eliminato")
        else:
            if a_idx < len(profile.animations):
                anim = profile.animations[a_idx]
                if messagebox.askyesno("Conferma",
                                       f"Eliminare l'animazione '{anim.name}'?"):
                    del profile.animations[a_idx]
                    self.timeline.clear()
                    self._refresh_tree()
                    self._update_display()
                    self.info_lbl.config(text=f"Animazione '{anim.name}' eliminata")

    def load_frames(self):
        folder = Path(self.folder_var.get())
        prefix = self.code_var.get().strip().upper()
        if not folder.exists():
            messagebox.showwarning("Attenzione", "Scegli prima una cartella.")
            return
        if len(prefix) < 4:
            messagebox.showwarning("Attenzione", "Il prefisso deve essere di almeno 4 caratteri.")
            return

        all_files = []
        for ext in (".png", ".jpg", ".jpeg", ".gif"):
            all_files.extend(folder.glob(f"{prefix}*{ext}"))
        all_files.extend(folder.glob(f"{prefix}*.jpeg"))
        all_files = [f for f in all_files if 'spritesheet' not in f.name.lower()]

        if not all_files:
            self.info_lbl.config(text="Nessun file trovato")
            return

        groups = {}
        for f in all_files:
            stem = f.stem
            if len(stem) >= 6 and stem.startswith(prefix):
                letter = stem[4]
                angle_str = stem[5]
                if letter.isalpha() and angle_str.isdigit():
                    angle = int(angle_str)
                    figlio = stem[2:4]
                    if figlio not in groups:
                        groups[figlio] = {}
                    if letter not in groups[figlio]:
                        groups[figlio][letter] = {}
                    if angle not in groups[figlio][letter]:
                        groups[figlio][letter][angle] = []
                    groups[figlio][letter][angle].append(f)

        if not groups:
            self.info_lbl.config(text="Nessun file con formato valido")
            return

        anim = AnimationData(name="Temp", code=prefix[:2], frames=[])
        for figlio, letters in sorted(groups.items()):
            for letter, angles in sorted(letters.items()):
                frame_group = FrameGroup(letter=letter, angles=[])
                for angle, files in sorted(angles.items()):
                    f = files[0]
                    try:
                        rel_path = str(f.relative_to(self.project.root_path))
                    except:
                        rel_path = str(f)
                    frame_group.angles.append(AngleData(
                        angle=angle,
                        file=rel_path,
                        duration_ms=DEFAULT_DURATION_MS
                    ))
                anim.frames.append(frame_group)

        self.timeline.load_from_animation(anim, self.project.root_path)
        self.current_frame_idx = 0
        self._update_display()
        self._update_angle_dots()
        self.info_lbl.config(text=f"{len(self.timeline.frames)} frame caricati")

    def _update_display(self):
        if not self.timeline.frames:
            self.canvas.delete('all')
            self.time_lbl.config(text="0s 0ms 0tick")
            self.info_lbl.config(text="")
            self._update_angle_dots()
            return
        self._show_frame(self.current_frame_idx)
        self._sync_speed_spinbox()
        total_ms = self.timeline.get_total_ms()
        self.time_lbl.config(text=f"{total_ms / 1000:.2f}s  {total_ms}ms  {self.timeline.get_total_ticks()}tick")
        self._draw_thumbnails()
        self._update_angle_dots()

    def _sync_speed_spinbox(self):
        if self.timeline.frames:
            try:
                self.speed_var.set(self.timeline.get_frame_duration(self.current_frame_idx))
            except Exception:
                pass
        total_ms = self.timeline.get_total_ms()
        self.time_lbl.config(text=f"{total_ms / 1000:.2f}s  {total_ms}ms  {self.timeline.get_total_ticks()}tick")
        self._draw_thumbnails()
        self._update_angle_dots()
    def _viewer_zoom_in(self):
        if self.viewer_zoom_var.get() == "Fit":
            self.viewer_zoom_var.set(self.VIEWER_ZOOM_LABELS[3])  # 100%
        else:
            try:
                idx = self.VIEWER_ZOOM_LABELS.index(self.viewer_zoom_var.get())
                if idx < len(self.VIEWER_ZOOM_LABELS) - 1:
                    self.viewer_zoom_var.set(self.VIEWER_ZOOM_LABELS[idx + 1])
            except ValueError:
                pass
        self._update_display()

    def _viewer_zoom_out(self):
        if self.viewer_zoom_var.get() == "Fit":
            return
        try:
            idx = self.VIEWER_ZOOM_LABELS.index(self.viewer_zoom_var.get())
            if idx > 0:
                self.viewer_zoom_var.set(self.VIEWER_ZOOM_LABELS[idx - 1])
            else:
                self.viewer_zoom_var.set("Fit")
        except ValueError:
            pass
        self._update_display()

    def _show_frame(self, idx):
        if idx < 0 or idx >= len(self.timeline.frames):
            return
        frame = self.timeline.get_frame_image(idx)
        if not frame:
            return

        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 10:
            w = 400
        if h < 10:
            h = 300

        if self.viewer_zoom_var.get() == "Fit":
            scale = min((w - 20) / frame.width,
                        (h - 20) / frame.height,
                        4.0)
            scale = max(scale, 0.05)
        else:
            try:
                idx_z = self.VIEWER_ZOOM_LABELS.index(self.viewer_zoom_var.get())
                scale = self.VIEWER_ZOOM_LEVELS[idx_z]
            except ValueError:
                scale = 1.0

        disp = frame.resize((int(frame.width * scale),
                            int(frame.height * scale)),
                            Image.NEAREST)

        checker = Image.new("RGBA", disp.size, (255, 255, 255, 255))
        for y in range(0, disp.height, 8):
            for x in range(0, disp.width, 8):
                if ((x // 8) + (y // 8)) % 2 == 0:
                    for yy in range(min(8, disp.height - y)):
                        for xx in range(min(8, disp.width - x)):
                            checker.putpixel((x + xx, y + yy), (210, 210, 210, 255))

        checker.paste(disp, (0, 0), disp)
        self._tk_img = ImageTk.PhotoImage(checker)
        self.canvas.delete('all')
        self.canvas.create_image(w // 2, h // 2, anchor='center', image=self._tk_img)

    def _draw_thumbnails(self):
        self.thumb_canvas.delete('all')
        self.thumb_refs.clear()
        if not self.timeline.frames:
            return

        thumb_w, thumb_h = 48, 48
        spacing = 4
        total_w = len(self.timeline.frames) * (thumb_w + spacing) + 20
        self.thumb_canvas.config(scrollregion=(0, 0, total_w, thumb_h + 20))

        for i, frame_group in enumerate(self.timeline.frames):
            img = None
            for angle_data in frame_group.angles:
                if angle_data.angle == self.timeline.current_angle:
                    img = angle_data.image
                    break

            if not img:
                continue

            thumb = img.copy()
            thumb.thumbnail((thumb_w, thumb_h), Image.NEAREST)
            tk_img = ImageTk.PhotoImage(thumb)
            self.thumb_refs.append(tk_img)

            x = i * (thumb_w + spacing) + 10
            y = 6

            self.thumb_canvas.create_rectangle(x - 2, y - 2, x + thumb_w + 2, y + thumb_h + 2,
                                               fill='#2a2a2a', outline='')
            self.thumb_canvas.create_image(x, y, anchor='nw', image=tk_img)
            self.thumb_canvas.create_text(x + thumb_w // 2, y + thumb_h + 14,
                                          text=f"{frame_group.letter}",
                                          fill='#888888', font=('Segoe UI', 7, 'bold'))

            if i == self.current_frame_idx:
                self.thumb_canvas.create_rectangle(x - 3, y - 3, x + thumb_w + 3, y + thumb_h + 3,
                                                   outline='#ff3333', width=2)
                tri_x = x + thumb_w // 2
                tri_y = y + thumb_h + 4
                self.thumb_canvas.create_polygon(tri_x - 6, tri_y, tri_x + 6, tri_y,
                                                 tri_x, tri_y + 8,
                                                 fill='#ff3333', outline='')

            rect_id = self.thumb_canvas.create_rectangle(
                x - 4, y - 4, x + thumb_w + 4, y + thumb_h + 20,
                outline='', fill='', tags=(f'thumb_{i}',)
            )
            self.thumb_canvas.tag_bind(f'thumb_{i}', '<Button-1>',
                                       lambda e, idx=i: self._jump_to_frame(idx))

    def _jump_to_frame(self, idx):
        if 0 <= idx < len(self.timeline.frames):
            if self.is_playing:
                self._pause()
            self.current_frame_idx = idx
            self._update_display()
            self._update_angle_dots()

    def _play(self):
        if not self.timeline.frames:
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
        dur = self.timeline.get_frame_duration(self.current_frame_idx)
        self._after_id = self.root.after(dur, self._tick)

    def _on_speed_change(self, event=None):
        try:
            speed = int(self.speed_spin.get())
        except (ValueError, tk.TclError):
            return
        self.speed_var.set(speed)
        if self.timeline.frames:
            for i in range(len(self.timeline.frames)):
                self.timeline.set_duration(i, speed)
            self._update_display()
    
    def _on_speed_change_debounced(self, event=None):
        if hasattr(self, '_speed_debounce_id') and self._speed_debounce_id:
            self.root.after_cancel(self._speed_debounce_id)
        self._speed_debounce_id = self.root.after(500, self._on_speed_change)

    def _save_project(self):
        pm = ProjectManager()
        pm.current_project = self.project
        pm._save_project()
        self._last_save_time = time.time()
        if self._autosave_next_at:
            self._autosave_next_at = time.time() + getattr(self, '_autosave_interval', 120)
        self._autosave_warned = False
        self._autosave_warn_until = 0

    def _save_as(self):
        path = filedialog.asksaveasfilename(defaultextension=PROJECT_EXTENSION,
                                           filetypes=[("Sprite Project", f"*{PROJECT_EXTENSION}")])
        if path:
            path = Path(path)
            self.project.root_path = path.parent
            self.project.name = path.stem
            pm = ProjectManager()
            pm.current_project = self.project
            pm._save_project()
            self._last_save_time = time.time()

    def _show_about(self):
        messagebox.showinfo("Informazioni", f"{APP_NAME} v{APP_VERSION}\n\nLettore 2.5D con supporto angoli 1-8\nSpritesheet integrato\n© 2026 - Yagor Studio")

    def _open_spritesheet_tool(self):
        from .ui_spritesheet import SpritesheetWindow
        SpritesheetWindow(
            self.root,
            project=self.project,
            on_import=self._on_spritesheet_import
        )

    def _on_spritesheet_import(self, profile):
        self._refresh_tree()
        self._check_profiles()
        if profile.animations:
            anim = profile.animations[-1]
            self.timeline.load_from_animation(anim, self.project.root_path)
            self.current_frame_idx = 0
            self._update_display()
            self._update_angle_dots()
            self.info_lbl.config(text=f"{anim.name} ({len(self.timeline.frames)} frame)")

    def _go_to_welcome(self):
        self.main_frame.destroy()
        WelcomeScreen(self.root, self._on_project_loaded)

    def _on_project_loaded(self, project):
        self.project = project
        self._build_content()
        self.root.title(f"{APP_NAME} v{APP_VERSION} - {project.name}")