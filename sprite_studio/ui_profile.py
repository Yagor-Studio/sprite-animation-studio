# sprite_studio/ui_profile.py
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import json

from .models import ProfileData, AnimationData, FrameGroup, AngleData
from .project_manager import ProjectManager
from .constants import IMG_EXTENSIONS, DEFAULT_DURATION_MS

class CreateProfileDialog:
    def __init__(self, parent, project, on_complete):
        self.parent = parent
        self.project = project
        self.on_complete = on_complete

        self.window = tk.Toplevel(parent)
        self.window.title("Crea nuova libreria")
        self.window.geometry("650x550")
        self.window.configure(bg='#2b2b2b')
        self.window.resizable(False, False)
        self.window.focus_force()
        self.window.grab_set()

        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_w = parent.winfo_width()
        parent_h = parent.winfo_height()
        x = parent_x + (parent_w - 650) // 2
        y = parent_y + (parent_h - 550) // 2
        self.window.geometry(f"+{x}+{y}")

        self.profile_name = tk.StringVar()
        self.profile_code = tk.StringVar()
        self.root_path = tk.StringVar()
        self._groups = {}

        self._build_ui()
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        title = tk.Label(self.window, text="NUOVA LIBRERIA", font=('Segoe UI', 18, 'bold'),
                         bg='#2b2b2b', fg='#ffffff')
        title.pack(pady=(25, 15))

        name_frame = tk.Frame(self.window, bg='#2b2b2b')
        name_frame.pack(fill='x', padx=40, pady=8)

        tk.Label(name_frame, text="Nome libreria:", font=('Segoe UI', 11),
                 bg='#2b2b2b', fg='#cccccc').pack(anchor='w')
        name_entry = tk.Entry(name_frame, textvariable=self.profile_name, font=('Segoe UI', 11),
                              bg='#3a3a3a', fg='white', relief='flat', insertbackground='white')
        name_entry.pack(fill='x', pady=(3, 0))
        name_entry.bind('<KeyRelease>', self._on_name_change)
        name_entry.focus_set()

        code_frame = tk.Frame(self.window, bg='#2b2b2b')
        code_frame.pack(fill='x', padx=40, pady=5)

        tk.Label(code_frame, text="Codice libreria (2 caratteri):", font=('Segoe UI', 11),
                 bg='#2b2b2b', fg='#cccccc').pack(anchor='w')
        self.code_label = tk.Label(code_frame, text="", font=('Segoe UI', 14, 'bold'),
                                   bg='#2b2b2b', fg='#4a9eff')
        self.code_label.pack(anchor='w', pady=(3, 0))

        root_frame = tk.Frame(self.window, bg='#2b2b2b')
        root_frame.pack(fill='x', padx=40, pady=8)

        tk.Label(root_frame, text="Cartella root (cerca ricorsivamente):", font=('Segoe UI', 11),
                 bg='#2b2b2b', fg='#cccccc').pack(anchor='w')

        path_row = tk.Frame(root_frame, bg='#2b2b2b')
        path_row.pack(fill='x', pady=(3, 0))

        self.path_entry = tk.Entry(path_row, textvariable=self.root_path, font=('Segoe UI', 10),
                                   bg='#3a3a3a', fg='white', relief='flat', insertbackground='white')
        self.path_entry.pack(side='left', fill='x', expand=True)

        tk.Button(path_row, text="Sfoglia...", font=('Segoe UI', 10),
                  bg='#555555', fg='white', relief='flat', padx=10,
                  command=self._browse_root).pack(side='right', padx=(5, 0))

        preview_frame = ttk.LabelFrame(self.window, text="Anteprima", padding=10)
        preview_frame.pack(fill='both', expand=True, padx=40, pady=10)

        self.preview_listbox = tk.Listbox(preview_frame, bg='#3a3a3a', fg='#ffffff',
                                          font=('Segoe UI', 9), height=8, relief='flat')
        self.preview_listbox.pack(fill='both', expand=True)

        btn_frame = tk.Frame(self.window, bg='#2b2b2b')
        btn_frame.pack(fill='x', padx=40, pady=(10, 20))

        tk.Button(btn_frame, text="Annulla", font=('Segoe UI', 11),
                  bg='#555555', fg='white', relief='flat', padx=25, pady=8,
                  command=self._on_close).pack(side='right', padx=(0, 10))

        self.create_btn = tk.Button(btn_frame, text="Crea Libreria", font=('Segoe UI', 11, 'bold'),
                                    bg='#4a9eff', fg='white', relief='flat', padx=25, pady=8,
                                    command=self._create_profile, state='disabled')
        self.create_btn.pack(side='right')

    def _on_name_change(self, event):
        name = self.profile_name.get().strip()
        if name:
            words = name.split()
            if len(words) >= 2:
                code = (words[0][0] + words[1][0]).upper()
            else:
                code = name[:2].upper()
            if len(code) < 2:
                code = code + "X"
            self.profile_code.set(code)
            self.code_label.config(text=code)
            if self.root_path.get():
                self._scan_folder()
        else:
            self.profile_code.set("")
            self.code_label.config(text="")

    def _browse_root(self):
        path = filedialog.askdirectory(title="Seleziona la cartella root")
        if path:
            self.root_path.set(path)
            self._scan_folder()

    def _scan_folder(self):
        self.preview_listbox.delete(0, tk.END)
        root = Path(self.root_path.get())
        padre = self.profile_code.get()
        if not root.exists():
            self.create_btn.config(state='disabled')
            return
        if not padre:
            self.preview_listbox.insert(tk.END, "Genera prima il codice libreria.")
            self.create_btn.config(state='disabled')
            return

        all_images = []
        for ext in IMG_EXTENSIONS:
            all_images.extend(root.rglob(f"*{ext}"))
        all_images.extend(root.rglob("*.jpeg"))

        if not all_images:
            self.preview_listbox.insert(tk.END, "Nessun file immagine trovato.")
            self.create_btn.config(state='disabled')
            return

        groups = {}
        valid_files = 0

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
                        if figlio not in groups:
                            groups[figlio] = {}
                        if letter not in groups[figlio]:
                            groups[figlio][letter] = {}
                        if angle not in groups[figlio][letter]:
                            groups[figlio][letter][angle] = []
                        groups[figlio][letter][angle].append(f)
                        valid_files += 1

                        # Gestione doppia coppia per mirroring (2/8, 3/7, 4/6)
                        if len(stem) >= 8:
                            mirror_letter = stem[6]
                            mirror_angle_str = stem[7]
                            if mirror_letter.isalpha() and mirror_angle_str.isdigit():
                                mirror_angle = int(mirror_angle_str)
                                # Coppie valide: (2,8), (3,7), (4,6)
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

        if not groups or valid_files == 0:
            self.preview_listbox.insert(tk.END, "Nessun file valido trovato (formato: PADRE+FIGLIO+lettera+numero).")
            self.create_btn.config(state='disabled')
            return

        self.preview_listbox.insert(tk.END, f"Trovati {valid_files} file validi.")
        self.preview_listbox.insert(tk.END, f"Animazioni trovate: {len(groups)}")
        for figlio, letters in sorted(groups.items()):
            self.preview_listbox.insert(tk.END, f"\nAnimazione: {figlio}")
            for letter, angles in sorted(letters.items()):
                self.preview_listbox.insert(tk.END, f"  Frame {letter}: {len(angles)} angoli")
                angle_list = sorted(angles.keys())
                if len(angle_list) > 5:
                    self.preview_listbox.insert(tk.END, f"    Angoli: {angle_list[:3]} ... {angle_list[-2:]}")
                else:
                    self.preview_listbox.insert(tk.END, f"    Angoli: {angle_list}")

        self._groups = groups
        self.create_btn.config(state='normal')

    def _create_profile(self):
        if not self._groups:
            messagebox.showwarning("Attenzione", "Nessun file trovato da importare.")
            return

        name = self.profile_name.get().strip()
        code = self.profile_code.get()
        if not code:
            messagebox.showerror("Errore", "Codice libreria non generato.")
            return

        profile = ProfileData(name=name, code=code, animations=[])

        for figlio, letters in sorted(self._groups.items()):
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
                        # Determina se questo angolo è un mirror (doppia coppia)
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

        self.project.profiles.append(profile)

        pm = ProjectManager()
        pm.current_project = self.project
        pm._save_project()

        self.window.grab_release()
        self.window.destroy()
        self.on_complete(profile)

    def _on_close(self):
        self.window.grab_release()
        self.window.destroy()