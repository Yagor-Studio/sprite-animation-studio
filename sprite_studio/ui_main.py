# sprite_studio/ui_main.py
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from pathlib import Path
from PIL import Image, ImageTk
import re

from .constants import APP_NAME, APP_VERSION, DEFAULT_DURATION_MS, PROJECT_EXTENSION
from .models import AnimationData, FrameGroup, AngleData
from .timeline import TimelineModel
from .project_manager import ProjectManager
from .sprite_utils import build_pattern, sort_sprite_files, export_animation
from .ui_profile import CreateProfileDialog
from .ui_welcome import WelcomeScreen

class MainWindow:
    def __init__(self, parent, project):
        self.parent = parent
        self.project = project
        self.root = parent

        for child in parent.winfo_children():
            child.destroy()

        self.timeline = TimelineModel()
        self.current_frame_idx = 0
        self.is_playing = False
        self._after_id = None
        self.selected_thumb_index = -1
        self.drag_start_index = None

        self.code_var = tk.StringVar()
        self.folder_var = tk.StringVar(value=str(Path.cwd()))
        self.manual_files = []
        self.loop_var = tk.BooleanVar(value=True)
        self.anchor_var = tk.StringVar(value="bottom")
        self.speed_var = tk.IntVar(value=DEFAULT_DURATION_MS)

        self.main_frame = tk.Frame(parent, bg='#2b2b2b')
        self.main_frame.pack(fill='both', expand=True)

        self._build_menu()
        self._build_toolbar()
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
        file_menu.add_command(label="Esporta .pk3", command=self._export_pk3)
        file_menu.add_command(label="Esporta grid/sheet", command=self._export_sheet)
        file_menu.add_separator()
        file_menu.add_command(label="Torna al benvenuto", command=self._go_to_welcome)
        file_menu.add_command(label="Esci", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Informazioni", command=self._show_about)
        menubar.add_cascade(label="Aiuto", menu=help_menu)

    def _build_toolbar(self):
        toolbar = tk.Frame(self.main_frame, bg='#3a3a3a', height=35)
        toolbar.pack(fill='x', pady=(0, 5))

        tk.Label(toolbar, text=f"Progetto: {self.project.name}", bg='#3a3a3a',
                 fg='#888888', font=('Segoe UI', 10)).pack(side='left', padx=15)

        tk.Label(toolbar, text=f"Modalità: {self.project.mode}", bg='#3a3a3a',
                 fg='#4a9eff', font=('Segoe UI', 10, 'bold')).pack(side='left', padx=10)

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

    def _build_content(self):
        left_frame = ttk.Frame(self.main_frame, width=250)
        left_frame.pack(side='left', fill='y', padx=5, pady=5)

        ttk.Label(left_frame, text="Profili / Animazioni", font=('Segoe UI', 12, 'bold')).pack(pady=(5,0))

        self.tree = ttk.Treeview(left_frame, columns=('type',), show='tree', height=10)
        self.tree.pack(fill='both', expand=True, padx=5, pady=5)
        self.tree.bind('<<TreeviewSelect>>', self._on_tree_select)

        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill='x', padx=5, pady=2)
        ttk.Button(btn_frame, text="Nuovo Profilo", command=self._create_first_profile).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="Nuova Animazione", command=self._new_animation).pack(side='left', padx=2)

        right_frame = ttk.Frame(self.main_frame)
        right_frame.pack(side='left', fill='both', expand=True, padx=5, pady=5)

        # ---- Lettore 2.5D ----
        viewer_frame = ttk.LabelFrame(right_frame, text="Lettore 2.5D")
        viewer_frame.pack(fill='both', expand=True, pady=5)

        # Controlli angolo
        angle_frame = ttk.Frame(viewer_frame)
        angle_frame.pack(fill='x', padx=5, pady=5)

        # Usa grid per fissare le distanze
        angle_frame.columnconfigure(0, weight=0)  # freccia sinistra
        angle_frame.columnconfigure(1, weight=1)  # etichetta
        angle_frame.columnconfigure(2, weight=0)  # freccia destra

        self.btn_left = ttk.Button(angle_frame, text="◀", command=self._prev_angle)
        self.btn_left.grid(row=0, column=0, padx=5, pady=2, sticky='w')

        self.angle_label = ttk.Label(angle_frame, text="1 - frontale", foreground='#4a9eff', anchor='center')
        self.angle_label.grid(row=0, column=1, padx=5, pady=2, sticky='ew')

        self.btn_right = ttk.Button(angle_frame, text="▶", command=self._next_angle)
        self.btn_right.grid(row=0, column=2, padx=5, pady=2, sticky='e')

        # Canvas per l'anteprima
        self.canvas = tk.Canvas(viewer_frame, bg='#eee', height=150, highlightthickness=0)
        self.canvas.pack(fill='both', expand=True, padx=5, pady=5)

        # Player
        player_frame = ttk.Frame(viewer_frame)
        player_frame.pack(fill='x', padx=5, pady=5)

        ttk.Button(player_frame, text="▶ Play", command=self._play).pack(side='left', padx=2)
        ttk.Button(player_frame, text="⏸ Pausa", command=self._pause).pack(side='left', padx=2)
        ttk.Button(player_frame, text="⏹ Stop", command=self._stop).pack(side='left', padx=2)
        ttk.Checkbutton(player_frame, text="Loop", variable=self.loop_var).pack(side='left', padx=5)

        ttk.Label(player_frame, text="Vel. (ms):").pack(side='left', padx=(10,3))
        self.speed_spin = ttk.Spinbox(player_frame, from_=20, to=2000, increment=10, width=6, textvariable=self.speed_var)
        self.speed_spin.pack(side='left')
        self.speed_spin.bind('<KeyRelease>', self._on_speed_change)

        self.time_lbl = ttk.Label(player_frame, text="0s 0ms 0tick", foreground='#666')
        self.time_lbl.pack(side='right', padx=10)

        # Thumbnail
        thumb_frame = ttk.LabelFrame(right_frame, text="Timeline (frame)")
        thumb_frame.pack(fill='x', pady=5)

        self.thumb_canvas = tk.Canvas(thumb_frame, bg='#f0f0f0', height=80, highlightthickness=0)
        self.thumb_canvas.pack(fill='x', padx=5, pady=5)
        self.thumb_refs = []

        # Esporta
        export_frame = ttk.LabelFrame(right_frame, text="Esporta")
        export_frame.pack(fill='x', pady=5)

        row = ttk.Frame(export_frame)
        row.pack(fill='x', padx=5, pady=5)
        ttk.Button(row, text="Esporta .pk3", command=self._export_pk3).pack(side='left', padx=2)
        ttk.Button(row, text="Esporta Grid/Sheet", command=self._export_sheet).pack(side='left', padx=2)
        ttk.Button(row, text="Esporta GIF", command=self._export_gif).pack(side='left', padx=2)

        self._refresh_tree()
        self._check_profiles()

    # ==================== ANGOLI ====================

    def _prev_angle(self):
        """Freccia sinistra: va verso destra (1->2->3...)"""
        new_angle = self.timeline.current_angle + 1
        if new_angle > 8:
            new_angle = 1
        self._set_angle(new_angle)

    def _next_angle(self):
        """Freccia destra: va verso sinistra (1->8->7...)"""
        new_angle = self.timeline.current_angle - 1
        if new_angle < 1:
            new_angle = 8
        self._set_angle(new_angle)

    def _set_angle(self, angle):
        self.timeline.set_angle(angle)
        desc = self._get_angle_description(angle)
        self.angle_label.config(text=f"{angle} - {desc}")
        self._update_display()

    # ==================== OVERLAY ====================

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
                desc = self._get_angle_description(self.timeline.current_angle)
                self.angle_label.config(text=f"{self.timeline.current_angle} - {desc}")
                self._update_display()
                self.status_lbl.config(text=f"Caricata: {anim.name} ({len(self.timeline.frames)} frame)")

        CreateProfileDialog(self.root, self.project, on_profile_created)

    # ==================== METODI PRINCIPALI ====================

    def _on_tree_select(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        item = sel[0]
        parent = self.tree.parent(item)
        if not parent:
            return

        children = self.tree.get_children(parent)
        try:
            anim_idx = children.index(item)
        except ValueError:
            return

        profile_children = self.tree.get_children("")
        for p_item in profile_children:
            if p_item == parent:
                profile_children2 = self.tree.get_children(p_item)
                p_idx = profile_children2.index(parent) if parent in profile_children2 else 0
                if p_idx < len(self.project.profiles):
                    profile = self.project.profiles[p_idx]
                    if anim_idx < len(profile.animations):
                        anim = profile.animations[anim_idx]
                        self.timeline.load_from_animation(anim, self.project.root_path)
                        self.current_frame_idx = 0
                        self._update_display()
                        self.status_lbl.config(text=f"Caricata: {anim.name} ({len(self.timeline.frames)} frame)")
        self._refresh_tree()

    def _refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        for profile in self.project.profiles:
            profile_id = self.tree.insert("", "end", text=f"{profile.name} [{profile.code}]")
            for anim in profile.animations:
                self.tree.insert(profile_id, "end", text=f"  {anim.name} [{anim.code}]")
        self._check_profiles()

    def _new_animation(self):
        if not self.project.profiles:
            messagebox.showwarning("Attenzione", "Crea prima un profilo.")
            return

        name = simpledialog.askstring("Nome animazione", "Inserisci il nome:")
        if not name:
            return
        code = simpledialog.askstring("Codice animazione", "Codice (2 caratteri):")
        if not code or len(code) != 2:
            messagebox.showwarning("Attenzione", "Il codice deve essere di 2 caratteri.")
            return
        code = code.upper()

        anim = AnimationData(name=name, code=code, frames=[])
        self.project.profiles[0].animations.append(anim)
        self._refresh_tree()
        self._save_project()

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

        if not all_files:
            self.status_lbl.config(text="Nessun file trovato")
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
            self.status_lbl.config(text="Nessun file con formato valido")
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
        desc = self._get_angle_description(self.timeline.current_angle)
        self.angle_label.config(text=f"{self.timeline.current_angle} - {desc}")
        self._update_display()
        self.status_lbl.config(text=f"{len(self.timeline.frames)} frame caricati")

    def _update_display(self):
        if not self.timeline.frames:
            self.canvas.delete('all')
            self.time_lbl.config(text="0s 0ms 0tick")
            return
        self._show_frame(self.current_frame_idx)
        total_ms = self.timeline.get_total_ms()
        self.time_lbl.config(text=f"{total_ms/1000:.2f}s  {total_ms}ms  {self.timeline.get_total_ticks()}tick")
        self._draw_thumbnails()

    def _show_frame(self, idx):
        if idx < 0 or idx >= len(self.timeline.frames):
            return
        frame = self.timeline.get_frame_image(idx)
        if not frame:
            return

        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        if w < 10: w = 300
        if h < 10: h = 150
        scale = min((w-20)/frame.width, (h-20)/frame.height, 4.0)
        scale = max(scale, 0.05)
        disp = frame.resize((int(frame.width*scale), int(frame.height*scale)), Image.NEAREST)

        checker = Image.new("RGBA", disp.size, (255,255,255,255))
        for y in range(0, disp.height, 8):
            for x in range(0, disp.width, 8):
                if ((x//8)+(y//8)) % 2 == 0:
                    for yy in range(min(8, disp.height-y)):
                        for xx in range(min(8, disp.width-x)):
                            checker.putpixel((x+xx, y+yy), (210,210,210,255))

        checker.paste(disp, (0,0), disp)
        self._tk_img = ImageTk.PhotoImage(checker)
        self.canvas.delete('all')
        self.canvas.create_image(w//2, h//2, anchor='center', image=self._tk_img)

    def _draw_thumbnails(self):
        self.thumb_canvas.delete('all')
        self.thumb_refs.clear()
        if not self.timeline.frames:
            return
        thumb_w, thumb_h = 50, 50
        spacing = 6

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
            x = i * (thumb_w + spacing)
            self.thumb_canvas.create_image(x, 5, anchor='nw', image=tk_img)
            self.thumb_canvas.create_text(x+thumb_w//2, 55, text=f"{frame_group.letter}", font=('Segoe UI', 8, 'bold'))

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
        except:
            return
        if self.timeline.frames:
            for i in range(len(self.timeline.frames)):
                self.timeline.set_duration(i, speed)
            self._update_display()

    def _save_project(self):
        pm = ProjectManager()
        pm.current_project = self.project
        pm._save_project()
        self.status_lbl.config(text="Progetto salvato.")

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
            self.status_lbl.config(text=f"Progetto salvato come: {path.name}")

    def _export_pk3(self):
        messagebox.showinfo("PK3", "Funzionalità in sviluppo!")

    def _export_sheet(self):
        messagebox.showinfo("Grid/Sheet", "Funzionalità in sviluppo!")

    def _export_gif(self):
        if not self.timeline.frames:
            messagebox.showwarning("Attenzione", "Nessun frame da esportare.")
            return

        export_images = []
        durations = []
        for i in range(len(self.timeline.frames)):
            img = self.timeline.get_frame_image(i)
            if img:
                export_images.append(img)
                durations.append(self.timeline.get_frame_duration(i))

        if not export_images:
            messagebox.showwarning("Attenzione", "Nessuna immagine disponibile per l'angolo corrente.")
            return

        path = filedialog.asksaveasfilename(defaultextension=".gif", filetypes=[("GIF", "*.gif")])
        if path:
            try:
                export_animation(export_images, Path(path), "GIF", durations, self.loop_var.get())
                messagebox.showinfo("Fatto", f"Esportato: {path}")
            except Exception as e:
                messagebox.showerror("Errore", str(e))

    def _show_about(self):
        messagebox.showinfo("Informazioni", f"{APP_NAME} v{APP_VERSION}\n\nLettore 2.5D con supporto angoli 1-8\n© 2026 - Yagor Studio")

    def _go_to_welcome(self):
        self.main_frame.destroy()
        WelcomeScreen(self.root, self._on_project_loaded)

    def _on_project_loaded(self, project):
        self.project = project
        self._build_content()
        self.root.title(f"{APP_NAME} v{APP_VERSION} - {project.name}")