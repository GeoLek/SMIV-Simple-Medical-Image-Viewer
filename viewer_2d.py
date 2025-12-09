# viewer_2d.py

import tkinter as tk
from tkinter import BooleanVar, IntVar, Checkbutton, Scale
import numpy as np

import image_loader
import image_processing
from PIL import Image, ImageTk
import cv2


def create_2d_viewer(file_path, modality):
    """
    Opens a 2D viewer with:
      - A separate window for metadata info,
      - Slicers for 3D/4D data,
      - Mouse-wheel zoom around cursor (when Zoom is enabled),
      - Vertical layout of checkboxes & sliders below the image,
      - All image transformations are applied via image_processing.apply_all_processing().
    """
    # 1) Detect file type & metadata
    file_type, metadata_str = image_loader.detect_file_type_and_metadata(file_path)

    # 2) Create main viewer window
    viewer_window = tk.Toplevel()
    viewer_window.title(f"2D Viewer - {modality}")
    viewer_window.geometry("1000x800")

    # 2b) Create separate metadata window
    meta_window = tk.Toplevel(viewer_window)
    meta_window.title("Image Metadata")
    meta_label = tk.Label(meta_window, text=metadata_str, justify=tk.LEFT, font=("TkDefaultFont", 10))
    meta_label.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    # 3) Load the data array based on file_type
    if file_type == "DICOM":
        full_data = image_loader.load_dicom(file_path).astype(np.float32)
        if full_data.ndim == 2:
            full_data = np.expand_dims(full_data, axis=-1)

    elif file_type == "NIfTI":
        arr_ = image_loader.load_nifti(file_path)
        if arr_.ndim == 2:
            arr_ = np.expand_dims(arr_, axis=-1)
        full_data = arr_.astype(np.float32)

    elif file_type == "JPEG/PNG":
        arr_ = image_loader.load_jpeg_png(file_path)
        full_data = np.expand_dims(arr_, axis=-1)

    else:
        print("Error: Unsupported format or detection failed.")
        viewer_window.destroy()
        return

    # Force up to 4D => shape=(H, W, Z, T)
    while full_data.ndim < 4:
        full_data = np.expand_dims(full_data, axis=-1)

    H, W, Z, T_ = full_data.shape

    # State
    state = {
        "data": full_data,   # float32 up to 4D
        "z_idx": 0,
        "t_idx": 0,
        "zoom_factor": 1.0,
        "zoom_enabled": False,
        "last_mouse_x": 0,
        "last_mouse_y": 0,
    }

    # =========== UI LAYOUT ===========
    top_frame = tk.Frame(viewer_window)
    top_frame.pack(side=tk.TOP)

    # Canvas for image
    canvas = tk.Canvas(top_frame, width=W, height=H, bg="black")
    canvas.pack(side=tk.TOP)

    displayed_image = None  # keep reference

    # =========== SETTINGS (vertical layout) ===========
    bottom_frame = tk.Frame(viewer_window)
    bottom_frame.pack(side=tk.TOP, fill=tk.X)

    settings = {
        "hist_eq": BooleanVar(value=False),
        "colormap": BooleanVar(value=False),
        "brightness_contrast": BooleanVar(value=False),
        "brightness": IntVar(value=0),    # range -100..100
        "contrast": IntVar(value=1),      # range 1..5
    }

    # Checkbuttons
    c_hist = Checkbutton(bottom_frame, text="Histogram Equalization",
                         variable=settings["hist_eq"],
                         command=lambda: update_image())
    c_hist.pack(side=tk.TOP, anchor="w")

    c_cmap = Checkbutton(bottom_frame, text="Apply Colormap",
                         variable=settings["colormap"],
                         command=lambda: update_image())
    c_cmap.pack(side=tk.TOP, anchor="w")

    c_bc = Checkbutton(bottom_frame, text="Brightness/Contrast",
                       variable=settings["brightness_contrast"],
                       command=lambda: update_image())
    c_bc.pack(side=tk.TOP, anchor="w")

    # Sliders
    s_bright = Scale(bottom_frame, from_=-100, to=100,
                     label="Brightness",
                     variable=settings["brightness"],
                     orient=tk.HORIZONTAL,
                     command=lambda v: update_image())
    s_bright.pack(side=tk.TOP, fill=tk.X)

    s_contrast = Scale(bottom_frame, from_=1, to=5, resolution=0.1,
                       label="Contrast",
                       variable=settings["contrast"],
                       orient=tk.HORIZONTAL,
                       command=lambda v: update_image())
    s_contrast.pack(side=tk.TOP, fill=tk.X)

    var_zoom = BooleanVar(value=False)
    def toggle_zoom():
        state["zoom_enabled"] = var_zoom.get()
        update_image()

    c_zoom = Checkbutton(bottom_frame, text="Enable Mouse Zoom",
                         variable=var_zoom,
                         command=toggle_zoom)
    c_zoom.pack(side=tk.TOP, anchor="w")

    # If Z>1 or T>1, add slice sliders
    if Z > 1:
        z_slider = Scale(bottom_frame, from_=0, to=Z - 1,
                         label="Z Slice",
                         orient=tk.HORIZONTAL,
                         command=lambda val: update_z(int(val)))
        z_slider.pack(side=tk.TOP, fill=tk.X)

    if T_ > 1:
        t_slider = Scale(bottom_frame, from_=0, to=T_ - 1,
                         label="T Slice",
                         orient=tk.HORIZONTAL,
                         command=lambda val: update_t(int(val)))
        t_slider.pack(side=tk.TOP, fill=tk.X)

    def update_z(idx):
        state["z_idx"] = idx
        update_image()

    def update_t(idx):
        state["t_idx"] = idx
        update_image()

    # ========== MOUSE-WHEEL ZOOM ==========
    def on_mouse_wheel(event):
        if not state["zoom_enabled"]:
            return
        step = 1.1
        if event.delta > 0:
            state["zoom_factor"] *= step
        else:
            state["zoom_factor"] /= step

        # bound range
        state["zoom_factor"] = max(0.1, min(20.0, state["zoom_factor"]))

        # record mouse
        state["last_mouse_x"] = event.x
        state["last_mouse_y"] = event.y

        update_image()

    def generic_wheel(event, delta):
        class E: pass
        e = E()
        e.delta = delta
        e.x = event.x
        e.y = event.y
        on_mouse_wheel(e)

    viewer_window.bind("<MouseWheel>", on_mouse_wheel)       # Windows / many Linux
    viewer_window.bind("<Button-4>", lambda e: generic_wheel(e, +120))  # Some older Linux
    viewer_window.bind("<Button-5>", lambda e: generic_wheel(e, -120))

    # ========== PROCESS & DISPLAY ==========
    def update_image():
        """
        1) Extract current slice
        2) Pass to image_processing.apply_all_processing() with user settings
        3) Clip & show
        """
        # 1) Extract slice
        z_idx = state["z_idx"]
        t_idx = state["t_idx"]
        slice_2d = state["data"][:, :, z_idx, t_idx]
        img_array = slice_2d.copy()

        # 2) Call all transformations from image_processing
        processed = image_processing.apply_all_processing(
            img_array,
            hist_eq=settings["hist_eq"].get(),
            brightness_contrast=settings["brightness_contrast"].get(),
            brightness=float(settings["brightness"].get()),
            contrast=float(settings["contrast"].get()),
            colormap=settings["colormap"].get(),
            zoom_enabled=state["zoom_enabled"],
            zoom_factor=state["zoom_factor"],
            zoom_center_x=state["last_mouse_x"],
            zoom_center_y=state["last_mouse_y"]
        )

        # 3) Clip & show
        processed = np.clip(processed, 0, 255).astype(np.uint8)
        pil_img = Image.fromarray(processed)
        photo = ImageTk.PhotoImage(pil_img)

        nonlocal displayed_image
        displayed_image = photo
        canvas.config(width=processed.shape[1], height=processed.shape[0])
        canvas.create_image(0, 0, anchor="nw", image=photo)

    # initial
    update_image()
