# viewer_2d.py
import tkinter as tk
from tkinter import BooleanVar, IntVar, Checkbutton, Scale
from PIL import Image, ImageTk
import image_loader
import image_processing
import numpy as np

def create_2d_viewer(file_path, modality):
    """
    Opens the 2D viewer with interactive controls.
    We do real-time updates by re-processing the stored original array
    whenever a slider or checkbox changes.
    """
    viewer_window = tk.Toplevel()
    viewer_window.title(f"2D Viewer - {modality}")

    # -- Load the original data once --
    file_type = image_loader.detect_file_type(file_path)
    if file_type == "DICOM":
        original_array = image_loader.load_dicom(file_path)
    elif file_type == "NIfTI":
        full_nifti = image_loader.load_nifti(file_path)
        # We'll just display the middle slice in 2D
        z_mid = full_nifti.shape[2] // 2
        original_array = full_nifti[:, :, z_mid]
    elif file_type == "JPEG/PNG":
        original_array = image_loader.load_jpeg_png(file_path)
    else:
        print("Error: Unknown file format in create_2d_viewer.")
        return

    # We keep the original array in a dictionary so we can re-apply transformations from scratch
    state = {
        "original_array": original_array,  # float32
        "processed_array": None,           # updated each time
    }

    # Create a label to display the image
    img_label = tk.Label(viewer_window)
    img_label.pack()

    # ---------- SETTINGS ----------
    settings = {
        "hist_eq": BooleanVar(value=False),
        "colormap": BooleanVar(value=False),
        "brightness_contrast": BooleanVar(value=False),
        "zoom": BooleanVar(value=False),
        "brightness": IntVar(value=0),  # start at 0
        "contrast": IntVar(value=1),    # start at 1
        "zoom_factor": IntVar(value=1), # start at 1
    }

    # ---------- EVENT HANDLER ----------
    def update_image(*args):
        """
        Re-applies the pipeline to the original array each time
        a slider or checkbox changes.
        """
        # Convert to float32
        img_array = state["original_array"].copy()

        # 1) Histogram Equalization
        if settings["hist_eq"].get():
            img_array = image_processing.apply_histogram_equalization(img_array, enabled=True)
        else:
            img_array = image_processing.apply_histogram_equalization(img_array, enabled=False)

        # 2) Colormap
        if settings["colormap"].get():
            img_array = image_processing.apply_colormap(img_array, enabled=True)
        else:
            img_array = image_processing.apply_colormap(img_array, enabled=False)

        # 3) Brightness / Contrast
        if settings["brightness_contrast"].get():
            # slider might be in int, so convert to float for contrast
            brightness_val = float(settings["brightness"].get())
            contrast_val = float(settings["contrast"].get())
            img_array = image_processing.adjust_brightness_contrast(img_array,
                                                                     brightness=brightness_val,
                                                                     contrast=contrast_val,
                                                                     enabled=True)
        else:
            img_array = image_processing.adjust_brightness_contrast(img_array, enabled=False)

        # 4) Zoom
        if settings["zoom"].get():
            zf = float(settings["zoom_factor"].get())
            img_array = image_processing.apply_zoom(img_array, zoom_factor=zf, enabled=True)
        else:
            img_array = image_processing.apply_zoom(img_array, enabled=False)

        # Convert to uint8 for display
        img_array = np.clip(img_array, 0, 255).astype(np.uint8)

        # Update the label
        img_pil = Image.fromarray(img_array)
        img_tk = ImageTk.PhotoImage(img_pil)
        img_label.config(image=img_tk)
        img_label.image = img_tk

        state["processed_array"] = img_array

    # Checkboxes
    Checkbutton(viewer_window, text="Histogram Equalization", variable=settings["hist_eq"], command=update_image).pack()
    Checkbutton(viewer_window, text="Apply Colormap", variable=settings["colormap"], command=update_image).pack()
    Checkbutton(viewer_window, text="Brightness/Contrast", variable=settings["brightness_contrast"], command=update_image).pack()
    Checkbutton(viewer_window, text="Zoom", variable=settings["zoom"], command=update_image).pack()

    # Sliders
    Scale(viewer_window, from_=-100, to=100, label="Brightness", variable=settings["brightness"], orient="horizontal", command=update_image).pack()
    Scale(viewer_window, from_=1, to=5, label="Contrast", variable=settings["contrast"], orient="horizontal", command=update_image).pack()
    Scale(viewer_window, from_=1, to=5, label="Zoom", variable=settings["zoom_factor"], orient="horizontal", command=update_image).pack()

    # Initialize the image display
    update_image()
