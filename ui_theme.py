# ui_theme.py

import tkinter as tk
from tkinter import ttk

# Dark Theme Colors
THEME = {
    "bg": "#2B3A42",  # Steel Blue-Gray
    "text": "white",
    "button": "#738290",  # Soft Silver-Blue
    "button_hover": "#AEB6BF",
    "header": "#556D7F",
    "header_text": "white"
}

def apply_theme(root, buttons, header_frame, header_label, info_label):
    """ Apply the dark theme to the UI elements """
    root.config(bg=THEME["bg"])
    header_frame.config(bg=THEME["header"])
    header_label.config(bg=THEME["header"], fg=THEME["header_text"])
    info_label.config(bg=THEME["bg"], fg=THEME["text"])

    for btn in buttons:
        btn.config(bg=THEME["button"], fg=THEME["text"], activebackground=THEME["button_hover"])

def style_button(btn):
    """ Apply modern styling to buttons """
    btn.config(
        font=("Arial", 13, "bold"),
        fg=THEME["text"],
        bg=THEME["button"],
        activebackground=THEME["button_hover"],
        activeforeground="black",
        bd=3,
        relief="raised",
        width=22,
        height=2,
        cursor="hand2"
    )
    btn.bind("<Enter>", lambda e: btn.config(bg=THEME["button_hover"]))  # Hover effect
    btn.bind("<Leave>", lambda e: btn.config(bg=THEME["button"]))  # Restore color

def setup_ui(root, select_modality):
    """ Sets up the main UI with styling """
    root.title("SMIV: Simple Medical Image Viewer")
    root.geometry("600x600")  # Increased size
    root.configure(bg=THEME["bg"])

    # Header
    header_frame = tk.Frame(root, bg=THEME["header"], pady=20)
    header_frame.pack(fill=tk.X)

    header_label = tk.Label(
        header_frame, text="SMIV: Simple Medical Image Viewer", font=("Arial", 18, "bold"),
        fg=THEME["header_text"], bg=THEME["header"]
    )
    header_label.pack()

    # Info Text
    info_label = tk.Label(root, text="Select an Imaging Modality:", font=("Arial", 14),
                          fg=THEME["text"], bg=THEME["bg"])
    info_label.pack(pady=15)

    # Buttons
    buttons = []
    modalities = ["MRI", "CT", "PET/CT", "EUS"]  # Removed emojis

    for text in modalities:
        btn = tk.Button(root, text=text, command=lambda t=text: select_modality(t))
        style_button(btn)
        btn.pack(pady=10)
        buttons.append(btn)

    # Apply Initial Theme
    apply_theme(root, buttons, header_frame, header_label, info_label)

def apply_viewer_theme(root, exclude_widgets=None):
    """
    Apply the same theme to the viewer window (Toplevel) as the main menu.

    exclude_widgets: optional list of widget objects to skip (e.g., image_frame/image_label)
    """
    exclude = set(exclude_widgets or [])

    # ttk styling (Notebook, etc.)
    try:
        style = ttk.Style(root)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure("TFrame", background=THEME["bg"])
        style.configure("TLabel", background=THEME["bg"], foreground=THEME["text"])
        style.configure("TNotebook", background=THEME["bg"])
        style.configure("TNotebook.Tab", background=THEME["header"], foreground=THEME["header_text"])
        style.map("TNotebook.Tab", background=[("selected", THEME["button"])])
    except Exception:
        pass

    def _apply(w):
        if w in exclude:
            return

        # Root and containers
        if isinstance(w, (tk.Tk, tk.Toplevel, tk.Frame)):
            try:
                w.configure(bg=THEME["bg"])
            except Exception:
                pass

        # Labels
        if isinstance(w, tk.Label):
            try:
                w.configure(bg=THEME["bg"], fg=THEME["text"])
            except Exception:
                pass

        # Buttons
        if isinstance(w, tk.Button):
            try:
                w.configure(
                    bg=THEME["button"],
                    fg=THEME["text"],
                    activebackground=THEME["button_hover"],
                    activeforeground="black",
                )
            except Exception:
                pass

        # Checkbuttons
        if isinstance(w, tk.Checkbutton):
            try:
                w.configure(
                    bg=THEME["bg"],
                    fg=THEME["text"],
                    activebackground=THEME["bg"],
                    selectcolor=THEME["bg"],
                )
            except Exception:
                pass

        # Scales
        if isinstance(w, tk.Scale):
            try:
                w.configure(bg=THEME["bg"], fg=THEME["text"], troughcolor=THEME["button"])
            except Exception:
                pass

        # Canvas
        if isinstance(w, tk.Canvas):
            try:
                w.configure(bg=THEME["bg"], highlightthickness=0)
            except Exception:
                pass

        for c in w.winfo_children():
            _apply(c)

    _apply(root)
