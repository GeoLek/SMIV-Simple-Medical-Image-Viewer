# ui_theme.py

import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont

THEME = {
    "bg": "#2B3A42",
    "text": "white",
    "button": "#738290",
    "button_hover": "#AEB6BF",
    "header": "#556D7F",
    "header_text": "white",
}

FONTS = {
    "family": "Arial",
    "tab": ("Arial", 11, "bold"),
    "button": ("Arial", 10),
    "label": ("Arial", 10),
    "status": ("Arial", 9),
    "header": ("Arial", 18, "bold"),
    "primary_button": ("Arial", 14, "bold"),
    "secondary_button": ("Arial", 10),
}


def _pick_font_family(root) -> str:
    preferred = ["Segoe UI", "Helvetica", "Arial"]
    try:
        families = set(tkfont.families(root))
        for f in preferred:
            if f in families:
                return f
    except Exception:
        pass
    return "Arial"


def init_fonts(root):
    fam = _pick_font_family(root)
    FONTS["family"] = fam
    FONTS["tab"] = (fam, 11, "bold")
    FONTS["button"] = (fam, 10)
    FONTS["label"] = (fam, 10)
    FONTS["status"] = (fam, 9)
    FONTS["header"] = (fam, 18, "bold")
    FONTS["primary_button"] = (fam, 14, "bold")
    FONTS["secondary_button"] = (fam, 10)


def style_primary_button(btn):
    btn.config(
        font=FONTS["primary_button"],
        fg=THEME["text"],
        bg=THEME["button"],
        activebackground=THEME["button_hover"],
        activeforeground="black",
        bd=4,
        relief="raised",
        width=24,
        height=3,
        cursor="hand2",
    )
    btn.bind("<Enter>", lambda e: btn.config(bg=THEME["button_hover"]))
    btn.bind("<Leave>", lambda e: btn.config(bg=THEME["button"]))


def style_secondary_button(btn):
    btn.config(
        font=FONTS["secondary_button"],
        fg=THEME["text"],
        bg=THEME["button"],
        activebackground=THEME["button_hover"],
        activeforeground="black",
        bd=3,
        relief="raised",
        width=16,
        height=2,
        cursor="hand2",
    )
    btn.bind("<Enter>", lambda e: btn.config(bg=THEME["button_hover"]))
    btn.bind("<Leave>", lambda e: btn.config(bg=THEME["button"]))


def apply_viewer_theme(root, exclude_widgets=None):
    init_fonts(root)
    exclude = set(exclude_widgets or [])

    # ttk styling
    try:
        style = ttk.Style(root)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure("TFrame", background=THEME["bg"])
        style.configure("TLabel", background=THEME["bg"], foreground=THEME["text"], font=FONTS["label"])
        style.configure("TButton", font=FONTS["button"])
        style.configure("TCheckbutton", background=THEME["bg"], foreground=THEME["text"], font=FONTS["label"])

        style.configure("TNotebook", background=THEME["bg"])
        style.configure(
            "TNotebook.Tab",
            background=THEME["header"],
            foreground=THEME["header_text"],
            font=FONTS["tab"],
            padding=(10, 6),
        )
        style.map("TNotebook.Tab", background=[("selected", THEME["button"])])
    except Exception:
        pass

    def _apply(w):
        if w in exclude:
            return

        if isinstance(w, (tk.Tk, tk.Toplevel, tk.Frame, tk.LabelFrame)):
            try:
                w.configure(bg=THEME["bg"])
            except Exception:
                pass

        if isinstance(w, tk.Label):
            try:
                w.configure(bg=THEME["bg"], fg=THEME["text"], font=FONTS["label"])
            except Exception:
                pass

        if isinstance(w, tk.Button):
            try:
                w.configure(
                    bg=THEME["button"],
                    fg=THEME["text"],
                    activebackground=THEME["button_hover"],
                    activeforeground="black",
                    font=FONTS["button"],
                )
            except Exception:
                pass

        if isinstance(w, tk.Checkbutton):
            try:
                w.configure(
                    bg=THEME["bg"],
                    fg=THEME["text"],
                    activebackground=THEME["bg"],
                    selectcolor=THEME["bg"],
                    font=FONTS["label"],
                )
            except Exception:
                pass

        if isinstance(w, tk.Scale):
            try:
                w.configure(bg=THEME["bg"], fg=THEME["text"], troughcolor=THEME["button"], font=FONTS["label"])
            except Exception:
                pass

        if isinstance(w, tk.Canvas):
            try:
                w.configure(bg=THEME["bg"], highlightthickness=0)
            except Exception:
                pass

        for c in w.winfo_children():
            _apply(c)

    _apply(root)


def setup_ui(
    root,
    on_load_scan,
    on_open_folder,
    on_open_recent,
    on_clear_recent,
    dnd_available: bool = False,
):
    """
    Main menu UI:
      - Big primary button: "Load your scan"
      - Secondary buttons: Open Folder, Clear Recent
      - Recent files list (double-click)
      - Optional hint for Drag-and-Drop if available
    Returns widget references for main.py to refresh the recent list.
    """
    init_fonts(root)

    root.title("SMIV: Simple Medical Image Viewer")
    root.geometry("640x720")
    root.configure(bg=THEME["bg"])

    # Header
    header_frame = tk.Frame(root, bg=THEME["header"], pady=18)
    header_frame.pack(fill=tk.X)

    header_label = tk.Label(
        header_frame,
        text="SMIV: Simple Medical Image Viewer",
        font=FONTS["header"],
        fg=THEME["header_text"],
        bg=THEME["header"],
    )
    header_label.pack()

    body = tk.Frame(root, bg=THEME["bg"])
    body.pack(fill=tk.BOTH, expand=True, padx=18, pady=18)

    # Primary action
    primary_btn = tk.Button(body, text="Load your scan", command=on_load_scan)
    style_primary_button(primary_btn)
    primary_btn.pack(pady=(8, 16))

    # Secondary actions row
    sec_row = tk.Frame(body, bg=THEME["bg"])
    sec_row.pack(fill=tk.X, pady=(0, 10))

    open_folder_btn = tk.Button(sec_row, text="Open Folder", command=on_open_folder)
    style_secondary_button(open_folder_btn)
    open_folder_btn.pack(side=tk.LEFT)

    clear_recent_btn = tk.Button(sec_row, text="Clear Recent", command=on_clear_recent)
    style_secondary_button(clear_recent_btn)
    clear_recent_btn.pack(side=tk.LEFT, padx=(10, 0))

    # Recent files section
    recent_title = tk.Label(body, text="Recent files", font=FONTS["label"], fg=THEME["text"], bg=THEME["bg"])
    recent_title.pack(anchor="w", pady=(14, 6))

    recent_frame = tk.Frame(body, bg=THEME["bg"])
    recent_frame.pack(fill=tk.BOTH, expand=True)

    lb = tk.Listbox(
        recent_frame,
        height=10,
        bg=THEME["bg"],
        fg=THEME["text"],
        selectbackground=THEME["button_hover"],
        selectforeground="black",
        font=FONTS["label"],
        highlightthickness=1,
        relief="solid",
    )
    lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    sb = tk.Scrollbar(recent_frame, orient=tk.VERTICAL, command=lb.yview)
    sb.pack(side=tk.RIGHT, fill=tk.Y)
    lb.configure(yscrollcommand=sb.set)

    hint_label = tk.Label(body, text="No recent files yet.", font=FONTS["status"], fg=THEME["text"], bg=THEME["bg"])
    hint_label.pack(anchor="w", pady=(6, 0))

    dnd_text = "Drag-and-drop is enabled. Drop a file or folder here to open."
    dnd_text_off = "Tip: Install 'tkinterdnd2' to enable drag-and-drop open."
    dnd_label = tk.Label(
        body,
        text=(dnd_text if dnd_available else dnd_text_off),
        font=FONTS["status"],
        fg=THEME["text"],
        bg=THEME["bg"],
    )
    dnd_label.pack(anchor="w", pady=(10, 0))

    def _open_selected_recent(_event=None):
        sel = lb.curselection()
        if not sel:
            return
        idx = int(sel[0])
        path = lb.get(idx)
        if callable(on_open_recent):
            on_open_recent(path)

    lb.bind("<Double-Button-1>", _open_selected_recent)
    lb.bind("<Return>", _open_selected_recent)

    # Apply theme to all widgets
    apply_viewer_theme(root)

    return {
        "recent_listbox": lb,
        "recent_hint_label": hint_label,
    }
