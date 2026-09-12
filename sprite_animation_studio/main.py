# sprite_studio/main.py
#!/usr/bin/env python3
import tkinter as tk
from tkinter import messagebox
import traceback

from .constants import APP_NAME, APP_VERSION
from .ui_welcome import WelcomeScreen
from .ui_main import MainWindow


def _report_callback_exception(self, exc, val, tb):
    traceback.print_exception(exc, val, tb)
    try:
        messagebox.showerror("Errore interno", f"{exc.__name__}: {val}")
    except Exception:
        pass


tk.Tk.report_callback_exception = _report_callback_exception


def main():
    root = tk.Tk()
    root.title(f"{APP_NAME} v{APP_VERSION}")
    root.geometry("1600x1000")
    root.minsize(1200, 800)
    root.configure(bg='#1a1a1a')
    root.state('zoomed')

    root.protocol("WM_DELETE_WINDOW", root.quit)
    root.lower()
    root.focus_force()

    def on_project_loaded(project):
        for child in root.winfo_children():
            child.destroy()
        MainWindow(root, project)
        root.title(f"{APP_NAME} v{APP_VERSION} - {project.name}")
        root.focus_force()

    WelcomeScreen(root, on_project_loaded)
    root.mainloop()


if __name__ == "__main__":
    main()