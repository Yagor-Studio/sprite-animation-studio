# sprite_animation_studio/ui_welcome.py
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
from datetime import datetime
import os
import subprocess
import sys

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None

from .constants import APP_NAME, APP_VERSION, PROJECT_EXTENSION
from .project_manager import ProjectManager, ProjectAlreadyExists
from .logger import log, open_log_folder


def _open_folder_in_explorer(path: str) -> None:
    """Apre la cartella nel file manager di sistema."""
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


def ask_load_backup_dialog(parent, corrupt_path: Path,
                           backup_path: Path, backup_date: str) -> str:
    """Finestra modale. Ritorna 'load_backup' o 'abort'."""
    win = tk.Toplevel(parent)
    win.title("Progetto corrotto")
    win.geometry("600x380")
    win.configure(bg='#2b2b2b')
    win.transient(parent)
    win.grab_set()
    win.resizable(False, False)
    win.focus_force()

    # Centra rispetto alla finestra padre
    parent.update_idletasks()
    px = parent.winfo_x() + (parent.winfo_width() - 600) // 2
    py = parent.winfo_y() + (parent.winfo_height() - 380) // 2
    win.geometry(f"+{px}+{py}")

    tk.Label(win, text="Progetto corrotto",
             font=('Segoe UI', 14, 'bold'),
             bg='#2b2b2b', fg='#ffffff').pack(pady=(20, 10))

    text = (
        f"Il file principale non è leggibile:\n"
        f"{corrupt_path}\n\n"
        f"È stato rinominato in:\n"
        f"{corrupt_path}\n\n"
        f"Il backup del {backup_date} è disponibile.\n\n"
        f"Vuoi caricare il backup? Il file principale verrà ricostruito a\n"
        f"partire dal backup, e il file corrotto resterà a parte."
    )
    tk.Label(win, text=text, font=('Segoe UI', 9),
             bg='#2b2b2b', fg='#aaaaaa',
             justify='center', wraplength=540).pack(padx=30)

    # Chiusura con la X equivale ad Annulla
    result = {'value': "abort"}

    def choose(value):
        result['value'] = value
        win.grab_release()
        win.destroy()

    btn_frame = tk.Frame(win, bg='#2b2b2b')
    btn_frame.pack(pady=25)

    tk.Button(btn_frame, text="Carica il backup",
              font=('Segoe UI', 10, 'bold'),
              bg='#4a9eff', fg='white', relief='flat',
              padx=18, pady=10,
              command=lambda: choose("load_backup")).pack(side='left', padx=6)

    tk.Button(btn_frame, text="Annulla",
              font=('Segoe UI', 10),
              bg='#555555', fg='white', relief='flat',
              padx=18, pady=10,
              command=lambda: choose("abort")).pack(side='left', padx=6)

    # Apre la cartella dei log senza chiudere il dialog
    tk.Button(btn_frame, text="Apri cartella log",
              font=('Segoe UI', 10),
              bg='#555555', fg='white', relief='flat',
              padx=18, pady=10,
              command=open_log_folder).pack(side='left', padx=6)

    # Invio = pulsante di default, Esc = Annulla
    win.bind('<Return>', lambda e: choose("load_backup"))
    win.bind('<Escape>', lambda e: choose("abort"))

    parent.wait_window(win)
    return result['value']


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

    def _ask_existing_project_action(self, sas_path):
        """Dialog per gestire un progetto già esistente: mostra una scheda
        con i dati del progetto e chiede cosa fare.
        Ritorna: 'open' | 'overwrite' | None (annulla).
        """
        # Lettura in sola lettura: _try_load non tocca file né recenti.
        # Se fallisce il dialog si apre comunque, in modalità degradata:
        # "Apri esistente" deve restare la via d'accesso al recupero C-09.
        pm = ProjectManager()
        existing = pm._try_load(sas_path)
        is_readable = existing is not None

        if is_readable:
            folder = str(sas_path.parent)
            try:
                created = datetime.fromisoformat(existing.created).strftime("%d/%m/%Y %H:%M")
            except (TypeError, ValueError):
                # Formato inatteso o campo vuoto: mostra il valore grezzo
                created = existing.created or "—"
            try:
                last_saved = datetime.fromtimestamp(
                    sas_path.stat().st_mtime).strftime("%d/%m/%Y %H:%M")
            except OSError:
                last_saved = "sconosciuto"
            num_profiles = len(existing.profiles)
            num_animations = sum(len(p.animations) for p in existing.profiles)
            num_frames = sum(len(a.frames) for p in existing.profiles for a in p.animations)

            rows = [
                ("Nome", existing.name),
                ("Percorso", folder),
                ("Creato", created),
                ("Librerie", str(num_profiles)),
                ("Animazioni", str(num_animations)),
                ("Frame totali", str(num_frames)),
                ("Ultimo salvataggio", last_saved),
            ]

        win = tk.Toplevel(self.window)
        win.title("Progetto già esistente")
        win.configure(bg='#2b2b2b')
        win.transient(self.window)
        win.grab_set()
        win.resizable(False, False)
        win.focus_force()

        tk.Label(win, text="Progetto già esistente",
                 font=('Segoe UI', 14, 'bold'),
                 bg='#2b2b2b', fg='#ffffff').pack(pady=(20, 12))

        if is_readable:
            # Scheda informativa: font monospace per allineare le colonne
            info = tk.Frame(win, bg='#1e1e1e', padx=16, pady=12)
            info.pack(fill='x', padx=30)

            for row, (label, value) in enumerate(rows):
                tk.Label(info, text=f"{label}:", font=('Consolas', 10),
                         bg='#1e1e1e', fg='#888888',
                         anchor='w').grid(row=row, column=0, sticky='nw',
                                          padx=(0, 12), pady=1)
                value_label = tk.Label(info, text=value, font=('Consolas', 10),
                                       bg='#1e1e1e', fg='#ffffff',
                                       anchor='w', justify='left', wraplength=400)
                value_label.grid(row=row, column=1, sticky='w', pady=1)
                if label == "Percorso":
                    # Percorso cliccabile: apre la cartella nel file manager
                    value_label.configure(fg='#4a9eff', cursor='hand2')
                    value_label.bind('<Button-1>',
                                     lambda e: _open_folder_in_explorer(folder))
        else:
            # Modalità degradata: al posto della scheda, solo l'avviso
            warning = ("⚠ Il progetto esistente è illeggibile.\n"
                       "Puoi aprirlo per tentare il recupero dal backup, "
                       "oppure sovrascriverlo per crearne uno nuovo.")
            tk.Label(win, text=warning, font=('Segoe UI', 10),
                     bg='#2b2b2b', fg='#ff8080',
                     wraplength=520, justify='left',
                     anchor='w').pack(fill='x', padx=30)

        result = {'value': None}

        def choose(mode):
            result['value'] = mode
            win.grab_release()
            win.destroy()

        btn_frame = tk.Frame(win, bg='#2b2b2b')
        btn_frame.pack(pady=(20, 10))

        btn_style = dict(font=('Segoe UI', 10), fg='white', relief='flat',
                         padx=14, pady=8)

        tk.Button(btn_frame, text="Crea copia", bg='#555555',
                  state='disabled', disabledforeground='#888888',
                  **btn_style).grid(row=0, column=0, padx=5)
        tk.Label(btn_frame, text="in arrivo", font=('Segoe UI', 8),
                 bg='#2b2b2b', fg='#888888').grid(row=1, column=0)

        tk.Button(btn_frame, text="Apri esistente", bg='#555555',
                  command=lambda: choose("open"),
                  **btn_style).grid(row=0, column=1, padx=5, sticky='n')

        tk.Button(btn_frame, text="Crea nuovo (sovrascrive)", bg='#8b3a3a',
                  command=lambda: choose("overwrite"),
                  **btn_style).grid(row=0, column=2, padx=5, sticky='n')

        tk.Button(btn_frame, text="Annulla", bg='#555555',
                  command=lambda: choose(None),
                  **btn_style).grid(row=0, column=3, padx=5, sticky='n')

        hint = ("Sovrascrivendo, il progetto attuale verrà copiato in\n"
                f"{sas_path.stem}.sas.overwritten_<timestamp>.bak "
                "prima di essere sostituito.\n"
                "I PNG degli sprite restano intatti sul disco.")
        tk.Label(win, text=hint, font=('Segoe UI', 8),
                 bg='#2b2b2b', fg='#888888',
                 justify='center', wraplength=520).pack(padx=30, pady=(0, 14))

        # Centra rispetto alla finestra principale; la dimensione dipende
        # dal contenuto (un percorso lungo va a capo su più righe)
        self.window.update_idletasks()
        win.update_idletasks()
        w, h = win.winfo_reqwidth(), win.winfo_reqheight()
        px = self.window.winfo_x() + (self.window.winfo_width() - w) // 2
        py = self.window.winfo_y() + (self.window.winfo_height() - h) // 2
        win.geometry(f"+{px}+{py}")

        self.window.wait_window(win)
        return result['value']

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

        try:
            project = pm.create_project(root_path, name, mode)
        except ProjectAlreadyExists as e:
            choice = self._ask_existing_project_action(e.path)
            if choice is None:
                # Annulla: torna alla finestra senza fare nulla
                return
            if choice == "open":
                # Traccia l'annullamento volontario del recupero backup, per
                # non mostrare un errore quando l'utente ha solo premuto Annulla.
                aborted = {"value": False}

                def on_corrupt(c, b, d):
                    result = ask_load_backup_dialog(self.window, c, b, d)
                    if result != "load_backup":
                        aborted["value"] = True
                    return result

                project = pm.load_project(e.path, on_corrupt=on_corrupt)
                if project is None:
                    if aborted["value"]:
                        log.info(f"Apertura progetto esistente annullata dall'utente: {e.path.name}")
                        return
                    messagebox.showerror(
                        "Errore",
                        "Impossibile aprire il progetto esistente.\n"
                        "Il file potrebbe essere danneggiato."
                    )
                    return
            elif choice == "overwrite":
                try:
                    project = pm.create_project(root_path, name, mode, force=True)
                except Exception as ex:
                    messagebox.showerror(
                        "Errore",
                        f"Impossibile creare il progetto:\n{ex}"
                    )
                    return

        self.window.grab_release()
        self.window.destroy()
        self.on_complete(project)

    def _on_close(self):
        self.window.grab_release()
        self.window.destroy()


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
        try:
            icon_path = self._get_resource_path("resources/icon.ico")
            if icon_path.exists():
                self.window.iconbitmap(str(icon_path))
        except Exception:
            pass
        self.window.focus_force()
        self.window.grab_set()

        self._build_ui()
        self.window.protocol("WM_DELETE_WINDOW", self._close_app)
        self.window.bind('<Escape>', lambda e: self._close_app())
        self.window.bind('<Alt-F4>', lambda e: self._close_app())
        self.window.focus_set()

    def _get_resource_path(self, relative_path):
        if getattr(sys, 'frozen', False):
            base_path = Path(sys._MEIPASS)
        else:
            base_path = Path(__file__).parent
        return base_path / relative_path

    def _build_ui(self):
        left_frame = tk.Frame(self.window, bg='#2b2b2b', width=386, height=530)
        left_frame.pack(side='left', fill='both', expand=True)

        right_frame = tk.Frame(self.window, bg='#3a3a3a', width=579, height=530)
        right_frame.pack(side='right', fill='both', expand=True)

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

        try:
            img_path = self._get_resource_path("resources/images/welcome_bg.png")
            if img_path.exists() and Image:
                img = Image.open(img_path)
                img = img.resize((579, 530), Image.Resampling.LANCZOS)
                self._bg_image = ImageTk.PhotoImage(img)
                bg_label = tk.Label(right_frame, image=self._bg_image, bg='#3a3a3a')
                bg_label.pack(fill='both', expand=True)
            else:
                self._draw_gradient(right_frame)
        except:
            self._draw_gradient(right_frame)

        close_btn = tk.Button(self.window, text="✕", font=('Segoe UI', 10, 'bold'),
                              bg='#2b2b2b', fg='#888888', relief='flat', padx=8, pady=2,
                              command=self._close_app)
        close_btn.place(relx=1.0, x=-8, y=8, anchor='ne')

    def _draw_gradient(self, parent):
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
        # Traccia se l'utente ha annullato il dialog di recupero backup,
        # per distinguere l'annullamento volontario da un fallimento vero.
        aborted = {"value": False}

        def on_corrupt(c, b, d):
            result = ask_load_backup_dialog(self.window, c, b, d)
            if result != "load_backup":
                aborted["value"] = True
            return result

        project = self.project_manager.load_project(path, on_corrupt=on_corrupt)
        if project:
            self._close()
            self.on_project_loaded(project)
            return

        if aborted["value"]:
            # Annullamento volontario: nessun errore, riporta la welcome in primo piano.
            log.info(f"Caricamento progetto annullato dall'utente: {path.name}")
            self.window.lift()
            self.window.focus_force()
            try:
                self.window.grab_set()
            except tk.TclError:
                pass
            return

        messagebox.showerror("Errore", "Impossibile caricare il progetto.")
        self.window.lift()
        self.window.focus_force()
        try:
            self.window.grab_set()
        except tk.TclError:
            pass

    def _close(self):
        self.window.grab_release()
        self.window.destroy()

    def _close_app(self):
        self._close()
        self.parent.quit()