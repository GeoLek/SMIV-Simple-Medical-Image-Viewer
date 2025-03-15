import tkinter as tk
from tkinter import BooleanVar, IntVar, Checkbutton, Scale
from PIL import Image, ImageTk
import image_loader
import image_processing
import numpy as np

def create_2d_viewer(file_path, modality):
    """
    Opens the 2D viewer with interactive controls (hist eq, colormap, brightness, etc.).
    Also supports:
      - mouse-wheel zoom (when 'Zoom' is enabled),
      - 3D/4D data by letting the user choose slices in Z (and T if present).
    """
    viewer_window = tk.Toplevel()
    viewer_window.title(f"2D Viewer - {modality}")

    file_type = image_loader.detect_file_type(file_path)

    # 1) Load the data
    if file_type == "DICOM":
        full_data = image_loader.load_dicom(file_path)  # 2D or maybe 3D multi-frame
        # Convert to float32
        full_data = full_data.astype(np.float32)
        # DICOM single file is usually 2D; if it's shape=(frames, height, width), we handle below.
        if len(full_data.shape) == 2:
            # Make it shape [height, width, 1] for easier slicing logic
            full_data = np.expand_dims(full_data, axis=-1)
        elif len(full_data.shape) == 3:
            # Could be (frames, height, width) or (height, width, frames)
            # We'll assume (height, width, frames) for consistency
            # If the data is reversed, you can reorder via np.transpose
            pass
    elif file_type == "NIfTI":
        arr_ = image_loader.load_nifti(file_path)
        # NIfTI can be 2D, 3D, or 4D
        if arr_.ndim == 2:
            # shape = (height, width)
            arr_ = arr_.astype(np.float32)
            arr_ = np.expand_dims(arr_, axis=-1)  # [H, W, 1]
            full_data = arr_
        elif arr_.ndim == 3:
            # shape = (X, Y, Z)
            full_data = arr_.astype(np.float32)
        elif arr_.ndim == 4:
            # shape = (X, Y, Z, T)
            full_data = arr_.astype(np.float32)
        else:
            print(f"Unsupported dimension: {arr_.shape}")
            viewer_window.destroy()
            return
    elif file_type == "JPEG/PNG":
        arr_ = image_loader.load_jpeg_png(file_path)  # [H, W], float32
        # Make it [H, W, 1]
        full_data = np.expand_dims(arr_, axis=-1)
    else:
        print("Error: Unknown file format.")
        viewer_window.destroy()
        return

    # For consistent indexing, ensure at least 3D: (H, W, D, T?) => up to 4D
    while full_data.ndim < 3:
        full_data = np.expand_dims(full_data, axis=-1)  # pad dims
    # Now we can handle up to 4D => shape (H, W, Z, T?)

    # We store everything in a dictionary
    state = {
        "data": full_data,          # up to 4D float32
        "slice_z": 0,               # current Z index
        "slice_t": 0,               # current T index
        "zoom_factor": 1.0,
        "last_mouse_x": 0,
        "last_mouse_y": 0,
    }

    shape = full_data.shape
    height, width = shape[0], shape[1]
    depth_z = 1
    depth_t = 1
    if len(shape) >= 3:
        depth_z = shape[2]
    if len(shape) == 4:
        depth_t = shape[3]

    # ---------- SETTINGS (checkboxes, brightness, etc.) ----------
    settings = {
        "hist_eq": BooleanVar(value=False),
        "colormap": BooleanVar(value=False),
        "brightness_contrast": BooleanVar(value=False),
        "zoom_enabled": BooleanVar(value=False),
        "brightness": IntVar(value=0),
        "contrast": IntVar(value=1),
    }

    # Make the main frame
    main_frame = tk.Frame(viewer_window)
    main_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    # Canvas for displaying the image
    canvas = tk.Canvas(main_frame, width=width, height=height)
    canvas.pack()

    # We'll keep a reference to the displayed PhotoImage
    displayed_image = None

    # ---------- SLICER UI (if >1 in Z or T) ----------
    def on_z_slider(val):
        state["slice_z"] = int(val)
        update_image()

    def on_t_slider(val):
        state["slice_t"] = int(val)
        update_image()

    # Create frames for slice sliders
    if depth_z > 1:
        z_slider = tk.Scale(viewer_window, from_=0, to=depth_z - 1, label="Z-Slice", orient="horizontal",
                            command=on_z_slider)
        z_slider.pack()
    if depth_t > 1:
        t_slider = tk.Scale(viewer_window, from_=0, to=depth_t - 1, label="T-Slice", orient="horizontal",
                            command=on_t_slider)
        t_slider.pack()

    # ---------- EVENT HANDLER FOR PROCESSING ----------
    def update_image(*args):
        """
        Re-applies pipeline (hist eq, brightness/contrast, colormap),
        slices the data at [slice_z, slice_t], then applies zoom if enabled.
        """
        # 1) Extract the current slice
        z = state["slice_z"]
        t = state["slice_t"] if depth_t > 1 else 0

        if depth_t > 1:
            # shape: (H, W, Z, T)
            slice_2d = state["data"][:, :, z, t]
        else:
            # shape: (H, W, Z)
            slice_2d = state["data"][:, :, z]

        # Convert to a working copy
        img_array = slice_2d.copy()

        # 2) Apply hist eq
        if settings["hist_eq"].get():
            img_array = image_processing.apply_histogram_equalization(img_array, enabled=True)
        else:
            img_array = image_processing.apply_histogram_equalization(img_array, enabled=False)

        # 3) Brightness/Contrast
        if settings["brightness_contrast"].get():
            b = float(settings["brightness"].get())
            c = float(settings["contrast"].get())
            img_array = image_processing.adjust_brightness_contrast(img_array, brightness=b, contrast=c, enabled=True)
        else:
            img_array = image_processing.adjust_brightness_contrast(img_array, enabled=False)

        # 4) Colormap
        if settings["colormap"].get():
            img_array = image_processing.apply_colormap(img_array, enabled=True)
        else:
            img_array = image_processing.apply_colormap(img_array, enabled=False)

        # 5) Zoom if checkbox is on
        if settings["zoom_enabled"].get():
            img_array = apply_zoom_centered(img_array,
                                            state["zoom_factor"],
                                            state["last_mouse_x"],
                                            state["last_mouse_y"])
        else:
            # If zoom not enabled, no zoom => factor = 1
            pass

        # Convert to 8-bit
        img_array = np.clip(img_array, 0, 255).astype(np.uint8)

        # Show on canvas
        from PIL import Image, ImageTk
        pil_img = Image.fromarray(img_array)
        photo = ImageTk.PhotoImage(pil_img)

        nonlocal displayed_image
        displayed_image = photo
        canvas.config(width=img_array.shape[1], height=img_array.shape[0])
        canvas.create_image(0, 0, anchor="nw", image=photo)

    # -------------- ZOOM WITH MOUSE WHEEL --------------
    def on_mouse_wheel(event):
        """
        If zoom is enabled, scroll up => zoom in, scroll down => zoom out,
        around the mouse cursor location (event.x, event.y).
        """
        if not settings["zoom_enabled"].get():
            return  # if Zoom checkbox is off, ignore the wheel

        # Typically on Windows, event.delta is ±120. On some Linux, ±1
        step = 1.1
        if event.delta > 0:
            state["zoom_factor"] *= step
        else:
            state["zoom_factor"] /= step

        # keep it in [0.1 .. 20]
        state["zoom_factor"] = max(0.1, min(20.0, state["zoom_factor"]))

        # record mouse position => center of zoom
        state["last_mouse_x"] = event.x
        state["last_mouse_y"] = event.y

        update_image()

    # Some Linux distros use Button-4/5 for the wheel
    viewer_window.bind("<MouseWheel>", on_mouse_wheel)
    viewer_window.bind("<Button-4>", lambda e: generic_wheel(e, +120))
    viewer_window.bind("<Button-5>", lambda e: generic_wheel(e, -120))

    def generic_wheel(event, delta):
        class E:
            pass
        e = E()
        e.delta = delta
        e.x = event.x
        e.y = event.y
        on_mouse_wheel(e)

    # -------------- UI FOR CHECKBOXES & SLIDERS --------------
    controls_frame = tk.Frame(viewer_window)
    controls_frame.pack(side=tk.BOTTOM, fill=tk.X)

    Checkbutton(controls_frame, text="Histogram Equalization", variable=settings["hist_eq"], command=update_image).pack(side=tk.LEFT)
    Checkbutton(controls_frame, text="Apply Colormap", variable=settings["colormap"], command=update_image).pack(side=tk.LEFT)
    Checkbutton(controls_frame, text="Brightness/Contrast", variable=settings["brightness_contrast"], command=update_image).pack(side=tk.LEFT)
    Checkbutton(controls_frame, text="Zoom", variable=settings["zoom_enabled"], command=update_image).pack(side=tk.LEFT)

    # Brightness slider
    tk.Label(controls_frame, text="Brightness").pack(side=tk.LEFT)
    bright_slider = tk.Scale(controls_frame, from_=-100, to=100, orient=tk.HORIZONTAL, variable=settings["brightness"], command=update_image)
    bright_slider.pack(side=tk.LEFT)

    # Contrast slider
    tk.Label(controls_frame, text="Contrast").pack(side=tk.LEFT)
    contrast_slider = tk.Scale(controls_frame, from_=1, to=5, resolution=0.1, orient=tk.HORIZONTAL, variable=settings["contrast"], command=update_image)
    contrast_slider.pack(side=tk.LEFT)

    # ============== HELPER FOR ZOOM ==============
    def apply_zoom_centered(img_array, zoom_factor, center_x, center_y):
        """
        Crop around (center_x, center_y) by 1/zoom_factor,
        then scale back up to original size.
        """
        h, w = img_array.shape[:2]
        if zoom_factor == 1.0:
            return img_array

        crop_w = int(w / zoom_factor)
        crop_h = int(h / zoom_factor)

        x1 = int(center_x - crop_w // 2)
        y1 = int(center_y - crop_h // 2)
        x2 = x1 + crop_w
        y2 = y1 + crop_h

        # Clip to boundaries
        if x1 < 0:
            x1 = 0
        if y1 < 0:
            y1 = 0
        if x2 > w:
            x2 = w
        if y2 > h:
            y2 = h

        if x2 <= x1 or y2 <= y1:
            # zoom is too large or center is out of range
            return img_array

        cropped = img_array[y1:y2, x1:x2]
        # scale it back to (w, h)
        cropped_u8 = np.clip(cropped, 0, 255).astype(np.uint8)
        import cv2
        resized_u8 = cv2.resize(cropped_u8, (w, h), interpolation=cv2.INTER_LINEAR)
        return resized_u8.astype(np.float32)

    # Initial draw
    update_image()
