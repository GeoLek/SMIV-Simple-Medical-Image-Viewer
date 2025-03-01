import tkinter as tk
from tkinter import filedialog, Scale, IntVar, BooleanVar, Checkbutton
from PIL import Image, ImageTk
import image_loader
import image_processing


def open_file(img_label=None, settings=None):
    """ Opens a file dialog and displays the selected image with the selected processing options """
    file_path = filedialog.askopenfilename(filetypes=[("DICOM", "*.dcm"), ("NIfTI", "*.nii;*.nii.gz")])

    if file_path and img_label and settings:  # Ensure settings and label exist
        display_image(file_path, img_label, settings)


def display_image(file_path, img_label, settings):
    """ Loads and displays the selected DICOM/NIfTI image with optional processing """
    ext = file_path.split('.')[-1].lower()

    if ext == "dcm":
        img_array = image_loader.load_dicom(file_path)
    elif ext in ["nii", "nii.gz"]:
        img_array = image_loader.load_nifti(file_path)[:, :, image_loader.load_nifti(file_path).shape[2] // 2]
    else:
        return

    # Apply processing based on user selections
    if settings["hist_eq"].get():
        img_array = image_processing.apply_histogram_equalization(img_array)
    if settings["colormap"].get():
        img_array = image_processing.apply_colormap(img_array)
    if settings["brightness_contrast"].get():
        img_array = image_processing.adjust_brightness_contrast(img_array, brightness=settings["brightness"].get(), contrast=settings["contrast"].get())
    if settings["zoom"].get():
        img_array = image_processing.apply_zoom(img_array, zoom_factor=settings["zoom_factor"].get())

    img_pil = Image.fromarray(img_array.astype("uint8"))
    img_tk = ImageTk.PhotoImage(img_pil)

    img_label.config(image=img_tk)
    img_label.image = img_tk


def create_2d_viewer():
    """ Opens the 2D viewer with interactive controls """
    viewer_window = tk.Toplevel()
    viewer_window.title("2D Medical Image Viewer")

    img_label = tk.Label(viewer_window)
    img_label.pack()

    # User settings (checkboxes)
    settings = {
        "hist_eq": BooleanVar(value=False),
        "colormap": BooleanVar(value=False),
        "brightness_contrast": BooleanVar(value=False),
        "zoom": BooleanVar(value=False),
        "brightness": IntVar(value=30),
        "contrast": IntVar(value=1),
        "zoom_factor": IntVar(value=1),
    }

    # Checkboxes
    Checkbutton(viewer_window, text="Histogram Equalization", variable=settings["hist_eq"]).pack()
    Checkbutton(viewer_window, text="Apply Colormap", variable=settings["colormap"]).pack()
    Checkbutton(viewer_window, text="Brightness/Contrast", variable=settings["brightness_contrast"]).pack()
    Checkbutton(viewer_window, text="Zoom", variable=settings["zoom"]).pack()

    # Sliders
    Scale(viewer_window, from_=-100, to=100, label="Brightness", variable=settings["brightness"], orient="horizontal").pack()
    Scale(viewer_window, from_=1, to=3, label="Contrast", variable=settings["contrast"], orient="horizontal").pack()
    Scale(viewer_window, from_=1, to=3, label="Zoom", variable=settings["zoom_factor"], orient="horizontal").pack()

    # Open File Button - Now passes the correct parameters
    btn_open = tk.Button(viewer_window, text="Open File", command=lambda: open_file(img_label, settings))
    btn_open.pack()

    viewer_window.mainloop()