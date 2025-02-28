import tkinter as tk
from tkinter import filedialog, BooleanVar, Checkbutton
import viewer_3d
import image_processing


def open_3d_file(settings):
    """ Opens a file dialog and renders the selected 3D image with the selected processing options """
    file_path = filedialog.askopenfilename(filetypes=[("DICOM Series", "*.dcm"), ("NIfTI Files", "*.nii;*.nii.gz")])
    if file_path:
        viewer_3d.render_3d_image(file_path, settings)


def create_3d_viewer():
    """ Opens the 3D viewer with interactive controls """
    viewer_window = tk.Toplevel()
    viewer_window.title("3D Medical Image Viewer")

    settings = {
        "hist_eq": BooleanVar(value=False),
        "colormap": BooleanVar(value=False),
        "brightness_contrast": BooleanVar(value=False),
        "zoom": BooleanVar(value=False),
    }

    Checkbutton(viewer_window, text="Histogram Equalization", variable=settings["hist_eq"]).pack()
    Checkbutton(viewer_window, text="Apply Colormap", variable=settings["colormap"]).pack()
    Checkbutton(viewer_window, text="Brightness/Contrast", variable=settings["brightness_contrast"]).pack()
    Checkbutton(viewer_window, text="Zoom", variable=settings["zoom"]).pack()

    btn_open = tk.Button(viewer_window, text="Open File", command=lambda: open_3d_file(settings))
    btn_open.pack()

    viewer_window.mainloop()
