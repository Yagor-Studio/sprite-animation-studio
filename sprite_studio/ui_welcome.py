# sprite_studio/ui_welcome.py
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import sys

# Import per Pillow
from PIL import Image, ImageTk

from .constants import APP_NAME, APP_VERSION, PROJECT_EXTENSION
from .project_manager import ProjectManager


class WelcomeScreen:
    def __init__(self, parent, on_project_loaded):
        self.parent = parent
        self.on_project_loaded = on_project_loaded
        self.project_manager = ProjectManager()

        self.window = tk.Toplevel(parent)
        self.window.title("")
        self.window.overrideredirect(True)
        self.window.configure(bg='#2b2b2b')

        width, height = 965, 530
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.window.geometry(f"{width}x{height}+{x}+{y}")

        self.window.focus_force()
        self.window.grab_set()

        self._build_ui()
        self.window.protocol("WM_DELETE_WINDOW", self._close_app)

    def _get_resource_path(self, relative_path):
        """Ottiene il percorso corretto per le risorse sia in sviluppo che in esecuzione."""
        if getattr(sys, 'frozen', False):
            # Siamo in un eseguibile PyInstaller
            base_path = Path(sys._MEIPASS)
        else:
            # Siamo in sviluppo
            base_path = Path(__file__).parent.parent
        return base_path / relative_path

    def _build_ui(self):
        left_frame = tk.Frame(self.window, bg='#2b2b2b', width=386, height=530)
        left_frame.pack(side='left', fill='both', expand=True)

        right_frame = tk.Frame(self.window, bg='#3a3a3a', width=579, height=530)
        right_frame.pack(side='right', fill='both', expand=True)

        # ---- PARTE SINISTRA ----
        title = tk.Label(left_frame, text=APP_NAME, font=('Segoe UI', 22, 'bold'),
                         bg='#2b2b2b', fg='#ffffff')
        title.pack(pady=(40, 2))

        version = tk.Label(left_frame, text=f"v{APP_VERSION}", font=('Segoe UI', 10),
                           bg='#2b2b2b', fg='#888888')
        version.pack(pady=(0, 30))

        btn_new = tk.Button(left_frame, text="NUOVA LIBRERIA", font=('Segoe UI', 12, 'bold'),
                            bg='#4a9eff', fg='white', relief='flat', padx=30, pady=10,
                            command=self._new_project)
        btn_new.pack(pady=6)

        btn_open = tk.Button(left_frame, text="APRI LIBRERIA", font=('Segoe UI', 12, 'bold'),
                             bg='#555555', fg='white', relief='flat', padx=30, pady=10,
                             command=self._open_project)
        btn_open.pack(pady=6)

        recent_label = tk.Label(left_frame, text="RECENTI", font=('Segoe UI', 9, 'bold'),
                                bg='#2b2b2b', fg='#888888')
        recent_label.pack(anchor='w', padx=30, pady=(25, 3))

        self.recent_listbox = tk.Listbox(left_frame, bg='#3a3a3a', fg='#ffffff',
                                         font=('Segoe UI', 9), height=5,
                                         selectmode='single', relief='flat')
        self.recent_listbox.pack(fill='x', padx=30, pady=3)
        self.recent_listbox.bind('<Double-Button-1>', self._on_recent_double_click)

        footer = tk.Label(left_frame, text="© 2026 Yagor Studio", font=('Segoe UI', 8),
                          bg='#2b2b2b', fg='#555555')
        footer.pack(side='bottom', pady=10)

        self._update_recent_list()

        # ---- PARTE DESTRA ----
        try:
            # Usa la funzione per ottenere il percorso corretto
            img_path = self._get_resource_path("resources/images/welcome_bg.png")

            if img_path.exists():
                img = Image.open(img_path)
                # Ridimensiona per adattarsi al frame
                img = img.resize((579, 530), Image.Resampling.LANCZOS)
                self._bg_image = ImageTk.PhotoImage(img)

                bg_label = tk.Label(right_frame, image=self._bg_image, bg='#3a3a3a')
                bg_label.pack(fill='both', expand=True)
            else:
                # Se l'immagine non esiste, mostra il gradiente
                self._draw_gradient(right_frame)

        except Exception as e:
            print(f"Errore caricamento immagine: {e}")
            self._draw_gradient(right_frame)

        # Tasto chiudi
        close_btn = tk.Button(self.window, text="✕", font=('Segoe UI', 10, 'bold'),
                              bg='#2b2b2b', fg='#888888', relief='flat', padx=8, pady=2,
                              command=self._close_app)
        close_btn.place(x=930, y=8)

    def _draw_gradient(self, parent):
        """Disegna un gradiente come fallback."""
        canvas = tk.Canvas(parent, bg='#3a3a3a', highlightthickness=0)
        canvas.pack(fill='both', expand=True)

        for i in range(530):
            r = 40 + int((i / 530) * 20)
            g = 40 + int((i / 530) * 20)
            b = 50 + int((i / 530) * 30)
            color = f'#{r:02x}{g:02x}{b:02x}'
            canvas.create_line(0, i, 579, i, fill=color)

        canvas.create_text(290, 200, text="🎨", font=('Segoe UI', 80), fill='#555555')
        canvas.create_text(290, 280, text="Sprite Animation Studio", font=('Segoe UI', 16), fill='#666666')
        canvas.create_text(290, 310, text="Doom Sprite Editor", font=('Segoe UI', 11), fill='#555555')

    # -------------------- Metodi (invariati) --------------------

    def _update_recent_list(self):
        self.recent_listbox.delete(0, tk.END)
        recent = self.project_manager.get_recent()
        for p in recent:
            self.recent_listbox.insert(tk.END, f"{p.stem} ({p.parent.name})")

    def _on_recent_double_click(self, event):
        idx = self.recent_listbox.curselection()
        if idx:
            recent = self.project_manager.get_recent()
            if idx[0] < len(recent):
                self._load_project(recent[idx[0]])

    def _new_project(self):
        NewProjectWindow(self.window, self._on_project_created)

    def _on_project_created(self, project):
        self._close()
        self.on_project_loaded(project)

    def _open_project(self):
        file_path = filedialog.askopenfilename(
            title="Apri progetto",
            filetypes=[("Sprite Animation Studio", f"*{PROJECT_EXTENSION}")]
        )
        if file_path:
            self._load_project(Path(file_path))

    def _load_project(self, path: Path):
        project = self.project_manager.load_project(path)
        if project:
            self._close()
            self.on_project_loaded(project)
        else:
            messagebox.showerror("Errore", "Impossibile caricare il progetto.")

    def _close(self):
        self.window.grab_release()
        self.window.destroy()

    def _close_app(self):
        self._close()
        self.parent.quit()


class NewProjectWindow:
    def __init__(self, parent, on_complete):
        self.parent = parent
        self.on_complete = on_complete

        self.window = tk.Toplevel(parent)
        self.window.title("Nuovo Progetto")
        self.window.geometry("500x380")
        self.window.configure(bg='#2b2b2b')
        self.window.resizable(False, False)
        self.window.focus_force()
        self.window.grab_set()

        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_w = parent.winfo_width()
        parent_h = parent.winfo_height()
        x = parent_x + (parent_w - 500) // 2
        y = parent_y + (parent_h - 380) // 2
        self.window.geometry(f"+{x}+{y}")

        self.project_name = tk.StringVar()
        self.project_path = tk.StringVar()
        self.mode_var = tk.StringVar(value="DooMod")

        self._build_ui()
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        title = tk.Label(self.window, text="NUOVO PROGETTO", font=('Segoe UI', 16, 'bold'),
                         bg='#2b2b2b', fg='#ffffff')
        title.pack(pady=(25, 15))

        name_frame = tk.Frame(self.window, bg='#2b2b2b')
        name_frame.pack(fill='x', padx=40, pady=8)

        tk.Label(name_frame, text="Nome progetto:", font=('Segoe UI', 11),
                 bg='#2b2b2b', fg='#cccccc').pack(anchor='w')
        name_entry = tk.Entry(name_frame, textvariable=self.project_name, font=('Segoe UI', 11),
                              bg='#3a3a3a', fg='white', relief='flat', insertbackground='white')
        name_entry.pack(fill='x', pady=(3, 0))
        name_entry.focus_set()

        path_frame = tk.Frame(self.window, bg='#2b2b2b')
        path_frame.pack(fill='x', padx=40, pady=8)

        tk.Label(path_frame, text="Cartella di destinazione:", font=('Segoe UI', 11),
                 bg='#2b2b2b', fg='#cccccc').pack(anchor='w')

        path_row = tk.Frame(path_frame, bg='#2b2b2b')
        path_row.pack(fill='x', pady=(3, 0))

        self.path_entry = tk.Entry(path_row, textvariable=self.project_path, font=('Segoe UI', 10),
                                   bg='#3a3a3a', fg='white', relief='flat', insertbackground='white')
        self.path_entry.pack(side='left', fill='x', expand=True)

        tk.Button(path_row, text="Sfoglia...", font=('Segoe UI', 10),
                  bg='#555555', fg='white', relief='flat', padx=10,
                  command=self._browse_folder).pack(side='right', padx=(5, 0))

        mode_frame = tk.Frame(self.window, bg='#2b2b2b')
        mode_frame.pack(fill='x', padx=40, pady=12)

        tk.Label(mode_frame, text="Modalità:", font=('Segoe UI', 11),
                 bg='#2b2b2b', fg='#cccccc').pack(anchor='w', pady=(0, 5))

        mode_row = tk.Frame(mode_frame, bg='#2b2b2b')
        mode_row.pack(anchor='w')

        tk.Radiobutton(mode_row, text="DooMod", variable=self.mode_var, value="DooMod",
                       bg='#2b2b2b', fg='#ffffff', selectcolor='#2b2b2b',
                       font=('Segoe UI', 10)).pack(side='left', padx=(0, 20))

        tk.Radiobutton(mode_row, text="Animation", variable=self.mode_var, value="Animation",
                       bg='#2b2b2b', fg='#ffffff', selectcolor='#2b2b2b',
                       font=('Segoe UI', 10)).pack(side='left')

        btn_frame = tk.Frame(self.window, bg='#2b2b2b')
        btn_frame.pack(fill='x', padx=40, pady=(15, 20))

        tk.Button(btn_frame, text="Annulla", font=('Segoe UI', 11),
                  bg='#555555', fg='white', relief='flat', padx=25, pady=8,
                  command=self._on_close).pack(side='right', padx=(0, 10))

        tk.Button(btn_frame, text="Crea Progetto", font=('Segoe UI', 11, 'bold'),
                  bg='#4a9eff', fg='white', relief='flat', padx=25, pady=8,
                  command=self._create_project).pack(side='right')

    def _browse_folder(self):
        path = filedialog.askdirectory(title="Seleziona la cartella di destinazione")
        if path:
            self.project_path.set(path)

    def _create_project(self):
        name = self.project_name.get().strip()
        path = self.project_path.get().strip()

        if not name:
            messagebox.showwarning("Attenzione", "Inserisci un nome per il progetto.")
            return
        if not path:
            messagebox.showwarning("Attenzione", "Seleziona una cartella di destinazione.")
            return

        root_path = Path(path)
        if not root_path.exists():
            messagebox.showerror("Errore", "La cartella di destinazione non esiste.")
            return

        mode = self.mode_var.get()

        pm = ProjectManager()
        project = pm.create_project(root_path, name, mode)

        self.window.grab_release()
        self.window.destroy()
        self.on_complete(project)

    def _on_close(self):
        self.window.grab_release()
        self.window.destroy()