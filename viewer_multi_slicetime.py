import os
import tkinter as tk
from tkinter import ttk, BooleanVar, IntVar, Checkbutton, Scale
import nibabel as nib
import numpy as np
from PIL import Image, ImageTk

import image_loader
import image_processing


def create_viewer(file_paths, modality=""):
    """
    A viewer that:
      1) Navigates multiple files (Prev/Next).
      2) Navigates slices/time frames for 3D/4D images.
      3) Applies preprocessing (hist eq, brightness/contrast, colormap, zoom).
      4) Displays file metadata in a separate window.
    """

    root = tk.Toplevel()
    root.title("Multi-File, Multi-Slice/Time, Preprocessing Viewer")

    # ---------------------------------------------------------
    # State variables
    # ---------------------------------------------------------
    state = {
        "file_paths": file_paths,
        "current_file_index": 0,
        "volume": None,
        "z_index": 0,
        "t_index": 0,
        "z_max": 1,
        "t_max": 1,
        "zoom_factor": 1.0,
        "zoom_enabled": False
    }

    # Preprocessing toggles
    settings = {
        "hist_eq": BooleanVar(value=False),
        "colormap": BooleanVar(value=False),
        "brightness_contrast": BooleanVar(value=False),
        "brightness": IntVar(value=0),
        "contrast": IntVar(value=1),
    }

    # ---------------------------------------------------------
    # Helper Functions (defined before UI elements!)
    # ---------------------------------------------------------
    def display_current_slice():
        """ Display the slice at (z_index, t_index) with optional preprocessing. """
        vol = state["volume"]
        if vol is None:
            image_label.config(image="", text="Cannot display file", compound=tk.CENTER)
            return

        slice_2d = vol[..., state["z_index"], state["t_index"]]
        # Normalize to [0..255]
        min_val, max_val = slice_2d.min(), slice_2d.max()
        if max_val != min_val:
            slice_2d = (slice_2d - min_val)/(max_val - min_val)*255
        slice_2d = slice_2d.astype(np.float32)

        # Apply all processing
        out = image_processing.apply_all_processing(
            slice_2d,
            hist_eq=settings["hist_eq"].get(),
            brightness_contrast=settings["brightness_contrast"].get(),
            brightness=settings["brightness"].get(),
            contrast=settings["contrast"].get(),
            colormap=settings["colormap"].get(),
            zoom_enabled=state["zoom_enabled"],
            zoom_factor=state["zoom_factor"]
        )

        # Convert to PIL
        out = np.clip(out, 0, 255).astype(np.uint8)
        pil_img = Image.fromarray(out)
        tk_img = ImageTk.PhotoImage(pil_img)

        image_label.config(image=tk_img, text="", compound=tk.NONE)
        image_label.image = tk_img

    def load_current_file():
        """ Load the selected file, update metadata, and set up volume shape. """
        idx = state["current_file_index"]
        path = state["file_paths"][idx]
        file_type, meta_str = image_loader.detect_file_type_and_metadata(path)

        info_label.config(text=f"[{idx+1}/{len(file_paths)}] {os.path.basename(path)} - {file_type or 'Unknown'}")
        metadata_label.config(text=meta_str)

        if file_type == "DICOM":
            arr = image_loader.load_dicom(path)
            # Re-shape to 4D => (H, W, Z, T)
            if arr.ndim == 2:
                arr = arr[..., np.newaxis, np.newaxis]   # => (H, W, 1, 1)
            elif arr.ndim == 3:
                arr = arr[..., np.newaxis]               # => (H, W, Z, 1)
            state["volume"] = arr

        elif file_type == "NIfTI":
            vol = nib.load(path).get_fdata()
            if vol.ndim == 2:
                vol = vol[..., np.newaxis, np.newaxis]   # => (H, W, 1, 1)
            elif vol.ndim == 3:
                vol = vol[..., np.newaxis]               # => (H, W, Z, 1)
            state["volume"] = vol

        elif file_type == "JPEG/PNG":
            arr = image_loader.load_jpeg_png(path)
            arr = arr[..., np.newaxis, np.newaxis]       # => (H, W, 1, 1)
            state["volume"] = arr
        else:
            state["volume"] = None

        # Setup Z/T sliders
        if state["volume"] is not None:
            shape_4d = state["volume"].shape  # => (H, W, Z, T)
            state["z_max"] = shape_4d[2]
            state["t_max"] = shape_4d[3]
            # Reset indexes
            state["z_index"] = min(state["z_max"]//2, state["z_max"]-1)
            state["t_index"] = min(state["t_max"]//2, state["t_max"]-1)

            if state["z_max"] > 1:
                z_slider.config(to=state["z_max"] - 1)
                z_slider.set(state["z_index"])
                z_slider.pack(fill=tk.X, padx=10, pady=5)
            else:
                z_slider.pack_forget()

            if state["t_max"] > 1:
                t_slider.config(to=state["t_max"] - 1)
                t_slider.set(state["t_index"])
                t_slider.pack(fill=tk.X, padx=10, pady=5)
            else:
                t_slider.pack_forget()

        # Display
        display_current_slice()

    def change_file(delta):
        state["current_file_index"] = (state["current_file_index"] + delta) % len(file_paths)
        load_current_file()

    def update_z(val):
        state["z_index"] = val
        display_current_slice()

    def update_t(val):
        state["t_index"] = val
        display_current_slice()

    def toggle_zoom():
        state["zoom_enabled"] = zoom_var.get()
        display_current_slice()

    def on_mouse_wheel(event):
        if not state["zoom_enabled"]:
            return
        step = 1.1
        if event.delta > 0:
            state["zoom_factor"] *= step
        else:
            state["zoom_factor"] /= step
        state["zoom_factor"] = max(0.5, min(10.0, state["zoom_factor"]))
        display_current_slice()

    # ---------------------------------------------------------
    # Build UI elements (AFTER the helper functions)
    # ---------------------------------------------------------
    info_label = tk.Label(root, text="File Info", font=("Arial", 14))
    info_label.pack(pady=5)

    image_label = tk.Label(root)
    image_label.pack()

    nav_frame = tk.Frame(root)
    nav_frame.pack(pady=10)

    btn_prev_file = tk.Button(nav_frame, text="<< Prev File", command=lambda: change_file(-1))
    btn_prev_file.pack(side=tk.LEFT, padx=20)

    btn_next_file = tk.Button(nav_frame, text="Next File >>", command=lambda: change_file(+1))
    btn_next_file.pack(side=tk.LEFT, padx=20)

    z_slider = ttk.Scale(root, from_=0, to=0, orient="horizontal")
    t_slider = ttk.Scale(root, from_=0, to=0, orient="horizontal")

    # Add slider commands AFTER creation
    z_slider.config(command=lambda v: update_z(int(float(v))))
    t_slider.config(command=lambda v: update_t(int(float(v))))

    # Preprocessing frame
    preproc_frame = tk.Frame(root)
    preproc_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)

    cb_hist = Checkbutton(preproc_frame, text="Histogram Equalization", variable=settings["hist_eq"],
                          command=display_current_slice)
    cb_hist.pack(anchor="w")

    cb_colormap = Checkbutton(preproc_frame, text="Apply Colormap", variable=settings["colormap"],
                              command=display_current_slice)
    cb_colormap.pack(anchor="w")

    cb_bc = Checkbutton(preproc_frame, text="Brightness/Contrast", variable=settings["brightness_contrast"],
                        command=display_current_slice)
    cb_bc.pack(anchor="w")

    bright_scale = Scale(preproc_frame, from_=-100, to=100, label="Brightness", variable=settings["brightness"],
                         orient=tk.HORIZONTAL, command=lambda v: display_current_slice())
    bright_scale.pack(fill=tk.X)

    contrast_scale = Scale(preproc_frame, from_=1, to=5, resolution=0.1, label="Contrast", variable=settings["contrast"],
                           orient=tk.HORIZONTAL, command=lambda v: display_current_slice())
    contrast_scale.pack(fill=tk.X)

    zoom_var = BooleanVar(value=False)
    cb_zoom = Checkbutton(preproc_frame, text="Enable Zoom (mouse wheel)", variable=zoom_var, command=toggle_zoom)
    cb_zoom.pack(anchor="w")

    root.bind("<MouseWheel>", lambda e: on_mouse_wheel(e))

    # Metadata window
    metadata_win = tk.Toplevel(root)
    metadata_win.title("File Metadata")
    metadata_label = tk.Label(metadata_win, text="Metadata will appear here.", font=("Arial", 12), justify="left")
    metadata_label.pack(padx=10, pady=10)

    # Start with first file
    load_current_file()
    root.mainloop()
