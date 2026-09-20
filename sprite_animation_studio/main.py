# sprite_animation_studio/main.py
#!/usr/bin/env python3
import tkinter as tk
from tkinter import messagebox
import sys
import traceback

from .constants import APP_NAME, APP_VERSION
from .logger import log, get_log_path
from .ui_welcome import WelcomeScreen
from .ui_main import MainWindow
from pathlib import Path

# ----------------------------------------------------------------------
# GESTIONE ERRORI
# ----------------------------------------------------------------------

def _install_global_exception_handler():
    """Cattura qualsiasi eccezione non gestita (anche prima di Tk) e la logga."""
    def handler(exc_type, exc_value, exc_tb):
        log.critical("Eccezione non gestita",
                     exc_info=(exc_type, exc_value, exc_tb))
        try:
            messagebox.showerror(
                "Errore inatteso",
                f"Si è verificato un errore inatteso.\n\n"
                f"Dettagli salvati in:\n{get_log_path()}"
            )
        except Exception:
            pass

    sys.excepthook = handler


def _report_callback_exception(self, exc, val, tb):
    """Eccezioni dentro il loop Tkinter (callback)."""
    log.error("Eccezione in callback Tkinter",
              exc_info=(exc, val, tb))
    try:
        messagebox.showerror("Errore interno", f"{exc.__name__}: {val}")
    except Exception:
        pass


tk.Tk.report_callback_exception = _report_callback_exception


# ----------------------------------------------------------------------
# DPI
# ----------------------------------------------------------------------

def _enable_dpi_awareness():
    """Windows: dichiara che l'app gestisce il DPI nativamente."""
    if sys.platform != "win32":
        return
    import ctypes
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(
            ctypes.c_void_p(-4)
        )
    except (AttributeError, OSError):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except (AttributeError, OSError):
                pass

def _get_resource_path(relative_path):
    """Risolve il percorso di una risorsa sia in esecuzione da sorgente
    sia dentro l'eseguibile PyInstaller."""
    if getattr(sys, 'frozen', False):
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(__file__).parent
    return base_path / relative_path


def _set_window_icon(root):
    """Imposta l'icona della finestra e della taskbar.
    Deve essere chiamata dopo aver creato la finestra Tk."""
    try:
        icon_path = _get_resource_path("resources/icon.ico")
        if icon_path.exists():
            root.iconbitmap(str(icon_path))
        else:
            log.warning(f"Icona finestra non trovata: {icon_path}")
    except Exception as e:
        log.warning(f"Impossibile impostare icona finestra: {e}")
# ----------------------------------------------------------------------
# ENTRY POINT
# ----------------------------------------------------------------------

def main():
    _install_global_exception_handler()
    log.info(f"=== Avvio {APP_NAME} v{APP_VERSION} ===")

    _enable_dpi_awareness()

    root = tk.Tk()
    _set_window_icon(root)
    root.title(f"{APP_NAME} v{APP_VERSION}")
    root.geometry("1600x1000")
    root.minsize(900, 600)
    root.configure(bg='#1a1a1a')
    root.state('zoomed')

    root.protocol("WM_DELETE_WINDOW", root.quit)
    root.lower()
    root.focus_force()

    def on_project_loaded(project):
        log.info(f"Apertura progetto: {project.name}")
        for child in root.winfo_children():
            child.destroy()
        MainWindow(root, project)
        root.title(f"{APP_NAME} v{APP_VERSION} - {project.name}")
        root.focus_force()

    WelcomeScreen(root, on_project_loaded)
    root.mainloop()

    log.info("=== Chiusura applicazione ===")


if __name__ == "__main__":
    main()