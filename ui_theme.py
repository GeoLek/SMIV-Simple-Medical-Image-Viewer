# ui_theme.py
import tkinter as tk

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
