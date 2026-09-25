# sprite_animation_studio/ui_profile.py
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

from .models import ProfileData, AnimationData, FrameGroup, AngleData
from .project_manager import ProjectManager
from .constants import IMG_EXTENSIONS, DEFAULT_DURATION_MS

class CreateProfileDialog:
    def __init__(self, parent, project, on_complete, pre_commit=None):
        self.parent = parent
        self.project = project
        self.on_complete = on_complete
        self.pre_commit = pre_commit

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

        code_row = tk.Frame(code_frame, bg='#2b2b2b')
        code_row.pack(anchor='w', pady=(3, 0))

        self.code_entry = tk.Entry(code_row, textvariable=self.profile_code,
                                   font=('Segoe UI', 14, 'bold'),
                                   bg='#3a3a3a', fg='#4a9eff', relief='flat',
                                   insertbackground='white', width=4, justify='center')
        self.code_entry.pack(side='left')
        self.code_entry.bind('<KeyRelease>', self._on_code_change)

        self.code_warning = tk.Label(code_row, text="", font=('Segoe UI', 9),
                                     bg='#2b2b2b', fg='#ff5555')
        self.code_warning.pack(side='left', padx=8)

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
                base_code = (words[0][0] + words[1][0]).upper()
            else:
                base_code = name[:2].upper()
            if len(base_code) < 2:
                base_code = base_code + "X"

            # Proponi variante univoca se base_code è occupato
            proposed = self._propose_unique_code(base_code)
            self.profile_code.set(proposed)
            self._update_code_warning()

            if self.root_path.get():
                self._scan_folder()
        else:
            self.profile_code.set("")
            self.code_warning.config(text="")

    def _on_code_change(self, event=None):
        """L'utente ha modificato il codice a mano."""
        code = self.profile_code.get().strip().upper()
        # Forza maiuscolo e lunghezza 2
        if len(code) > 2:
            code = code[:2]
            self.profile_code.set(code)
        elif code != self.profile_code.get():
            self.profile_code.set(code)
        self._update_code_warning()

    def _propose_unique_code(self, base):
        """Ritorna un codice di 2 caratteri non usato da altri profili."""
        existing = {p.code.upper() for p in self.project.profiles}
        base = base[:2].upper()
        if base not in existing:
            return base

        # Prova varianti usando la seconda lettera della prima parola,
        # poi la terza, poi numeri
        name = self.profile_name.get().strip()
        letters = [c for c in name.upper() if c.isalpha()]
        first = base[0]

        for c in letters:
            candidate = (first + c)[:2]
            if candidate not in existing:
                return candidate

        # Ultima spiaggia: aggiungi numero
        for n in "0123456789":
            candidate = (first + n)[:2]
            if candidate not in existing:
                return candidate

        # Nessuna proposta disponibile (raro)
        return base

    def _update_code_warning(self):
        """Mostra un avviso se il codice è già usato."""
        code = self.profile_code.get().strip().upper()
        if not code or len(code) < 2:
            self.code_warning.config(text="")
            self.create_btn.config(state='disabled')
            return

        existing = {p.code.upper() for p in self.project.profiles}
        if code in existing:
            self.code_warning.config(text="⚠ codice già usato")
            self.create_btn.config(state='disabled')
        else:
            self.code_warning.config(text="✓")
            # Riabilita se tutti i requisiti sono soddisfatti
            self._refresh_create_button_state()

    def _refresh_create_button_state(self):
        """Abilita il pulsante Crea solo se tutti i requisiti sono soddisfatti."""
        name = self.profile_name.get().strip()
        code = self.profile_code.get().strip().upper()
        existing = {p.code.upper() for p in self.project.profiles}

        if not name or len(code) < 2 or code in existing:
            self.create_btn.config(state='disabled')
        else:
            self.create_btn.config(state='normal')

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
                        angle = int(rest[1])
                        if angle == 0:
                            angle = 1
                        groups.setdefault(figlio, {}).setdefault(letter, {}).setdefault(angle, []).append(f)
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

        if not groups or valid_files == 0:
            self.preview_listbox.insert(tk.END, "Nessun file valido trovato (formato: SPRITE+ANIMAZIONE+FRAME+COORDINATA).")
            self.preview_listbox.insert(tk.END, "La libreria verrà creata vuota.")
            self._groups = {}
            self._refresh_create_button_state()
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
        name = self.profile_name.get().strip()
        code = self.profile_code.get()
        if not code:
            messagebox.showerror("Errore", "Codice libreria non generato.")
            return

        folder_path = self.root_path.get()

        profile = ProfileData(name=name, code=code, animations=[], folder_path=folder_path)

        # Se ci sono gruppi (file), crea le animazioni
        if self._groups:
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
                            # Determina se è mirror
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
        # Se NON ci sono gruppi, la libreria rimane vuota (senza animazioni)
        if self.pre_commit:
            self.pre_commit()

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