# sprite_animation_studio/ui_settings.py
import tkinter as tk
from tkinter import ttk, messagebox

from .settings import Settings


class ShortcutCaptureDialog(tk.Toplevel):
    """Dialog che cattura una combinazione di tasti e la restituisce."""

    def __init__(self, parent, current=""):
        super().__init__(parent)
        self.result = None
        self.title("Premi la nuova combinazione")
        self.geometry("360x140")
        self.configure(bg='#2b2b2b')
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        tk.Label(self, text="Premi la combinazione di tasti",
                 font=('Segoe UI', 12, 'bold'), bg='#2b2b2b', fg='#ffffff').pack(pady=(20, 5))
        tk.Label(self, text=f"Attuale: {current}",
                 font=('Segoe UI', 10), bg='#2b2b2b', fg='#888888').pack()

        self.preview = tk.Label(self, text="…",
                                font=('Consolas', 14, 'bold'),
                                bg='#2b2b2b', fg='#4a9eff')
        self.preview.pack(pady=10)

        btn_bar = ttk.Frame(self)
        btn_bar.pack(pady=(0, 12))
        ttk.Button(btn_bar, text="Annulla",
                   command=self._cancel).pack(side='left', padx=4)

        self._confirm_id = None
        self.bind('<KeyPress>', self._on_key)
        self.focus_force()

    def _on_key(self, event):
        # Ignora solo i modificatori
        if event.keysym == "Escape":
            self._cancel()
            return

        # Ignora i modificatori isolati
        if event.keysym in ("Shift_L", "Shift_R", "Control_L", "Control_R",
                            "Alt_L", "Alt_R", "Meta_L", "Meta_R"):
            return

        parts = []
        if event.state & 0x4:  parts.append("Control")
        if event.state & 0x1:  parts.append("Shift")
        if event.state & 0x20000:
            parts.append("Alt")

        key = event.keysym
        if len(key) == 1:
            key = key.upper()

        if parts:
            combo = "<" + "-".join(parts + [key]) + ">"
        else:
            combo = f"<{key}>"

        self.result = combo
        self.preview.config(text=combo)
        self._confirm_id = self.after(250, self._confirm)

    def _cancel_pending_confirm(self):
        # Annulla il timer di auto-conferma, se in coda
        if self._confirm_id is not None:
            try:
                self.after_cancel(self._confirm_id)
            except Exception:
                pass
            self._confirm_id = None

    def _close(self):
        try:
            self.grab_release()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass

    def _confirm(self):
        self._confirm_id = None
        self._close()

    def _cancel(self):
        self._cancel_pending_confirm()
        self.result = None
        self._close()


class SettingsWindow:
    def __init__(self, parent):
        self.parent = parent
        self.settings = Settings()

        self.window = tk.Toplevel(parent)
        self.window.title("Impostazioni")
        self.window.geometry("520x460")
        self.window.configure(bg='#2b2b2b')
        self.window.transient(parent)
        self.window.grab_set()
        self.window.focus_force()

        self._build_ui()

    def _build_ui(self):
        nb = ttk.Notebook(self.window)
        nb.pack(fill='both', expand=True, padx=10, pady=10)

        # --- Tab Editor ---
        editor_tab = ttk.Frame(nb, padding=12)
        nb.add(editor_tab, text="Editor")

        self.autosave_var = tk.BooleanVar(
            value=bool(self.settings.get("editor", "autosave_enabled", False)))
        self.autosave_sec_var = tk.IntVar(
            value=int(self.settings.get("editor", "autosave_interval_sec", 120)))

        ttk.Checkbutton(editor_tab, text="Salvataggio automatico",
                        variable=self.autosave_var).pack(anchor='w', pady=(0, 8))

        row = ttk.Frame(editor_tab)
        row.pack(anchor='w', pady=4)
        ttk.Label(row, text="Intervallo (secondi):").pack(side='left')
        ttk.Spinbox(row, from_=15, to=3600, width=6,
                    textvariable=self.autosave_sec_var).pack(side='left', padx=6)


        row2 = ttk.Frame(editor_tab)
        row2.pack(anchor='w', pady=4)
        ttk.Label(row2, text="Profondità Undo (step):").pack(side='left')
        self.history_depth_var = tk.IntVar(
            value=int(self.settings.get("editor", "history_depth", 10)))
        ttk.Spinbox(row2, from_=1, to=100, width=6,
                    textvariable=self.history_depth_var).pack(side='left', padx=6)
        # --- Tab Shortcuts ---
        sc_tab = ttk.Frame(nb, padding=12)
        nb.add(sc_tab, text="Scorciatoie")

        self.shortcut_vars = {}
        shortcuts = self.settings.get("shortcuts")
        action_labels = {
            "save": "Salva progetto",
            "save_as": "Salva con nome",
            "open": "Apri progetto",
            "new": "Nuovo progetto",
            "undo": "Annulla (Undo)",
            "redo": "Ripeti (Redo)",
            "play": "Play",
            "pause": "Pausa",
            "stop": "Stop",
            "next_frame": "Frame successivo",
            "prev_frame": "Frame precedente",
            "next_angle": "Angolo successivo",
            "prev_angle": "Angolo precedente",
            "export": "Esporta animazione",
        }

        grid = ttk.Frame(sc_tab)
        grid.pack(fill='both', expand=True)

        self.shortcut_remove_buttons = {}
        self._action_labels = action_labels

        for i, (key, label) in enumerate(action_labels.items()):
            ttk.Label(grid, text=label).grid(row=i, column=0, sticky='w', pady=3)

            var = tk.StringVar(value=shortcuts.get(key, ""))
            self.shortcut_vars[key] = var

            ttk.Label(grid, textvariable=var, width=20,
                      foreground='#4a9eff').grid(row=i, column=1, sticky='w', padx=10)

            ttk.Button(grid, text="Cambia…",
                       command=lambda k=key: self._change_shortcut(k)
                       ).grid(row=i, column=2, padx=(4, 1))

            remove_btn = ttk.Button(grid, text="🗑", width=2,
                                     command=lambda k=key: self._remove_shortcut(k))
            remove_btn.grid(row=i, column=3, padx=(1, 4))
            self.shortcut_remove_buttons[key] = remove_btn
            self._update_remove_button_state(key)

            # Aggiorna lo stato del pulsante quando la scorciatoia cambia
            var.trace_add('write', lambda *_args, k=key: self._update_remove_button_state(k))

        # --- Bottoni ---
        btn_bar = ttk.Frame(self.window)
        btn_bar.pack(fill='x', padx=10, pady=(0, 10))

        ttk.Button(btn_bar, text="Salva", command=self._save).pack(side='right', padx=4)
        ttk.Button(btn_bar, text="Annulla", command=self.window.destroy).pack(side='right')

    def _change_shortcut(self, key):
        current = self.shortcut_vars[key].get()
        dlg = ShortcutCaptureDialog(self.window, current)
        self.window.wait_window(dlg)
        if dlg.result is not None:
            self.shortcut_vars[key].set(dlg.result)

    def _update_remove_button_state(self, key):
        # Il pulsante 🗑 è attivo solo se la scorciatoia non è vuota
        btn = self.shortcut_remove_buttons[key]
        has_shortcut = bool(self.shortcut_vars[key].get())
        btn.state(['!disabled'] if has_shortcut else ['disabled'])

    def _remove_shortcut(self, key):
        label = self._action_labels[key]
        if messagebox.askyesno(
                "Rimuovi scorciatoia",
                f"Rimuovere la scorciatoia per '{label}'?"):
            self.shortcut_vars[key].set("")

    def _save(self):
        self.settings.set("editor", "autosave_enabled", bool(self.autosave_var.get()))
        self.settings.set("editor", "autosave_interval_sec", int(self.autosave_sec_var.get()))
        self.settings.set("editor", "history_depth", int(self.history_depth_var.get()))
        for key, var in self.shortcut_vars.items():
            self.settings.set("shortcuts", key, var.get())

        # Avvisa MainWindow di ricaricare le impostazioni
        try:
            self.parent.event_generate('<<SettingsChanged>>', when='tail')
        except Exception:
            pass

        messagebox.showinfo("Impostazioni", "Salvate.")
        self.window.destroy()