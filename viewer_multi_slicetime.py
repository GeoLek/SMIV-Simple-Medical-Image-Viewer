# viewer_multi_slicetime.py

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
    Multi-file, multi-slice/time viewer with:
      - DICOM / NIfTI / PNG-JPG / TIFF / WHOLESLIDE
      - File slider + Prev/Next
      - Slice (Z) and time (T) sliders
      - Preprocessing: HistEq, Brightness/Contrast, Colormap
      - Zoom (mouse wheel) + Pan (left-drag)
    """

    root = tk.Toplevel()
    root.title("Multi-File, Multi-Slice/Time, Preprocessing Viewer (Zoom + Pan + TIFF/WSI)")

    # --------------------------------------------------------
    # Viewer state
    # --------------------------------------------------------
    state = {
        "file_paths": file_paths,
        "current_file_index": 0,
        "volume": None,      # 4D => (H, W, Z, T)
        "z_index": 0,
        "t_index": 0,
        "z_max": 1,
        "t_max": 1,
        "zoom_factor": 1.0,
        "zoom_enabled": False,
        # Pan / dragging state
        "pan_x": 0.0,        # offset of zoom center from image center (pixels)
        "pan_y": 0.0,
        "dragging": False,
        "drag_start_x": 0,
        "drag_start_y": 0,
        "drag_start_pan_x": 0.0,
        "drag_start_pan_y": 0.0,
    }

    # Preprocessing toggles/state
    settings = {
        "hist_eq": BooleanVar(value=False),
        "colormap": BooleanVar(value=False),
        "brightness_contrast": BooleanVar(value=False),
        "brightness": IntVar(value=0),
        "contrast": IntVar(value=1),
    }

    # --------------------------------------------------------
    # UI Layout
    # --------------------------------------------------------
    info_label = tk.Label(root, font=("Arial", 14))
    info_label.pack(pady=5)

    image_label = tk.Label(root)
    image_label.pack()

    # --- File navigation (Prev / Next + file slider)
    nav_frame = tk.Frame(root)
    nav_frame.pack(pady=10)

    def change_file(delta):
        new_idx = (state["current_file_index"] + delta) % len(file_paths)
        state["current_file_index"] = new_idx
        file_slider.set(new_idx)
        load_current_file()

    btn_prev = tk.Button(nav_frame, text="<< Prev File", command=lambda: change_file(-1))
    btn_prev.pack(side=tk.LEFT, padx=20)

    btn_next = tk.Button(nav_frame, text="Next File >>", command=lambda: change_file(+1))
    btn_next.pack(side=tk.LEFT, padx=20)

    def on_file_slider(val):
        idx = int(float(val))
        state["current_file_index"] = idx
        load_current_file()

    file_slider = ttk.Scale(
        root,
        from_=0,
        to=len(file_paths) - 1,
        orient="horizontal",
        command=on_file_slider
    )
    file_slider.pack(fill=tk.X, padx=10)

    # --- Z/T sliders
    z_slider = ttk.Scale(root, from_=0, to=0, orient="horizontal")
    t_slider = ttk.Scale(root, from_=0, to=0, orient="horizontal")

    def on_z_change(val):
        state["z_index"] = int(float(val))
        display_current_slice()

    def on_t_change(val):
        state["t_index"] = int(float(val))
        display_current_slice()

    z_slider.config(command=on_z_change)
    t_slider.config(command=on_t_change)

    # --- Preprocessing controls
    preproc_frame = tk.Frame(root)
    preproc_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)

    Checkbutton(
        preproc_frame,
        text="Histogram Equalization",
        variable=settings["hist_eq"],
        command=lambda: display_current_slice()
    ).pack(anchor="w")

    Checkbutton(
        preproc_frame,
        text="Apply Colormap",
        variable=settings["colormap"],
        command=lambda: display_current_slice()
    ).pack(anchor="w")

    Checkbutton(
        preproc_frame,
        text="Brightness/Contrast",
        variable=settings["brightness_contrast"],
        command=lambda: display_current_slice()
    ).pack(anchor="w")

    Scale(
        preproc_frame,
        from_=-100,
        to=100,
        label="Brightness",
        variable=settings["brightness"],
        orient=tk.HORIZONTAL,
        command=lambda x: display_current_slice()
    ).pack(fill=tk.X)

    Scale(
        preproc_frame,
        from_=1,
        to=5,
        resolution=0.1,
        label="Contrast",
        variable=settings["contrast"],
        orient=tk.HORIZONTAL,
        command=lambda x: display_current_slice()
    ).pack(fill=tk.X)

    zoom_var = BooleanVar(value=False)

    def toggle_zoom():
        state["zoom_enabled"] = zoom_var.get()
        # Reset pan when toggling zoom to avoid weird offsets
        state["pan_x"] = 0.0
        state["pan_y"] = 0.0
        state["zoom_factor"] = 1.0
        display_current_slice()

    Checkbutton(
        preproc_frame,
        text="Enable Zoom (wheel) + Pan (drag)",
        variable=zoom_var,
        command=toggle_zoom
    ).pack(anchor="w")

    # --- Metadata window
    metadata_win = tk.Toplevel(root)
    metadata_win.title("File Metadata")
    metadata_label = tk.Label(metadata_win, font=("Arial", 12), justify="left")
    metadata_label.pack(padx=10, pady=10)

    # --------------------------------------------------------
    # Zoom / Pan Event Handlers
    # --------------------------------------------------------
    def on_mouse_wheel(event):
        """Zoom in/out with the mouse wheel."""
        if not state["zoom_enabled"]:
            return
        step = 1.1
        direction = +1 if event.delta > 0 else -1
        if direction > 0:
            state["zoom_factor"] *= step
        else:
            state["zoom_factor"] /= step
        state["zoom_factor"] = max(0.5, min(10.0, state["zoom_factor"]))
        display_current_slice()

    def scroll_zoom(direction):
        """Support old Linux Button-4/5 events for zoom."""
        if not state["zoom_enabled"]:
            return
        step = 1.1
        if direction > 0:
            state["zoom_factor"] *= step
        else:
            state["zoom_factor"] /= step
        state["zoom_factor"] = max(0.5, min(10.0, state["zoom_factor"]))
        display_current_slice()

    def on_left_down(event):
        """Start panning if zoom is enabled."""
        if not state["zoom_enabled"]:
            return
        state["dragging"] = True
        state["drag_start_x"] = event.x
        state["drag_start_y"] = event.y
        state["drag_start_pan_x"] = state["pan_x"]
        state["drag_start_pan_y"] = state["pan_y"]

    def on_left_up(event):
        """Stop panning."""
        state["dragging"] = False

    def on_left_drag(event):
        """
        While dragging with left button:
        - Move pan_x / pan_y so that dragging feels like grabbing the image.
        - Dragging right => move view to the right (revealing right side),
          so the zoom center must shift to the LEFT (negative direction).
        """
        if not state["dragging"] or not state["zoom_enabled"]:
            return

        dx = event.x - state["drag_start_x"]
        dy = event.y - state["drag_start_y"]

        # Scale pan movement by zoom_factor so it doesn't feel too jumpy when zoomed in
        zf = state["zoom_factor"] if state["zoom_factor"] != 0 else 1.0

        # We invert the sign so that dragging right shows the right side (map-like behavior)
        state["pan_x"] = state["drag_start_pan_x"] - dx / zf
        state["pan_y"] = state["drag_start_pan_y"] - dy / zf

        display_current_slice()

    # --------------------------------------------------------
    # Loading / Display logic
    # --------------------------------------------------------
    def load_current_file():
        """Load current file into state['volume'] as a 4D array (H, W, Z, T)."""
        idx = state["current_file_index"]
        path = file_paths[idx]
        file_type, meta_str = image_loader.detect_file_type_and_metadata(path)

        info_label.config(
            text=f"[{idx+1}/{len(file_paths)}] {os.path.basename(path)} - {file_type or 'Unknown'}"
        )
        metadata_label.config(text=meta_str)

        arr = None

        if file_type == "DICOM":
            arr = image_loader.load_dicom(path)

        elif file_type == "NIfTI":
            vol = nib.load(path).get_fdata()
            arr = vol

        elif file_type == "JPEG/PNG":
            arr = image_loader.load_jpeg_png(path)

        elif file_type == "TIFF":
            arr = image_loader.load_tiff(path)

        elif file_type == "WHOLESLIDE":
            # Full-slide, downsampled to a manageable level,
            # but still a full-view image that we can preprocess.
            arr = image_loader.load_whole_slide_downsampled(path)

        # Convert arr to 4D (H, W, Z, T)
        if arr is not None:
            if arr.ndim == 2:
                # 2D => (H, W, 1, 1)
                arr = arr[..., np.newaxis, np.newaxis]
            elif arr.ndim == 3:
                # 3D => (H, W, Z, 1)
                arr = arr[..., np.newaxis]
            state["volume"] = arr
        else:
            state["volume"] = None

        if state["volume"] is not None:
            shape_4d = state["volume"].shape  # (H, W, Z, T)
            state["z_max"] = shape_4d[2]
            state["t_max"] = shape_4d[3]
            state["z_index"] = min(state["z_max"] // 2, state["z_max"] - 1)
            state["t_index"] = min(state["t_max"] // 2, state["t_max"] - 1)

            # Configure Z slider
            if state["z_max"] > 1:
                z_slider.config(to=state["z_max"] - 1)
                z_slider.set(state["z_index"])
                z_slider.pack(fill=tk.X, padx=10, pady=5)
            else:
                z_slider.pack_forget()

            # Configure T slider
            if state["t_max"] > 1:
                t_slider.config(to=state["t_max"] - 1)
                t_slider.set(state["t_index"])
                t_slider.pack(fill=tk.X, padx=10, pady=5)
            else:
                t_slider.pack_forget()
        else:
            state["z_max"] = 1
            state["t_max"] = 1
            z_slider.pack_forget()
            t_slider.pack_forget()

        # Reset zoom/pan when changing files
        state["zoom_factor"] = 1.0
        state["pan_x"] = 0.0
        state["pan_y"] = 0.0

        display_current_slice()

    def display_current_slice():
        """Grab current slice (H, W) from volume, preprocess, then show in Tk."""
        vol = state["volume"]
        if vol is None:
            image_label.config(image="", text="Cannot display file", compound=tk.CENTER)
            return

        # Extract 2D slice: (H, W, Z, T) -> (H, W)
        slice_2d = vol[..., state["z_index"], state["t_index"]]

        # Normalize to [0, 255] before processing
        slice_2d = slice_2d.astype(np.float32)
        min_val, max_val = slice_2d.min(), slice_2d.max()
        if max_val != min_val:
            slice_2d = (slice_2d - min_val) / (max_val - min_val) * 255.0

        # Apply preprocessing, zoom, and pan
        out = image_processing.apply_all_processing(
            slice_2d,
            hist_eq=settings["hist_eq"].get(),
            brightness_contrast=settings["brightness_contrast"].get(),
            brightness=settings["brightness"].get(),
            contrast=settings["contrast"].get(),
            colormap=settings["colormap"].get(),
            zoom_enabled=state["zoom_enabled"],
            zoom_factor=state["zoom_factor"],
            pan_x=state["pan_x"],
            pan_y=state["pan_y"],
        )

        out = np.clip(out, 0, 255).astype(np.uint8)

        # If colormap was applied, out may be (H, W, 3); otherwise (H, W)
        if out.ndim == 2:
            pil_img = Image.fromarray(out, mode="L")
        else:
            pil_img = Image.fromarray(out[..., ::-1], mode="RGB")  # BGR->RGB

        tk_img = ImageTk.PhotoImage(pil_img)
        image_label.config(image=tk_img, text="", compound=tk.NONE)
        image_label.image = tk_img

    # --------------------------------------------------------
    # Bind events and initialize
    # --------------------------------------------------------
    # Zoom (wheel)
    root.bind("<MouseWheel>", on_mouse_wheel)             # Windows/macOS
    root.bind("<Button-4>", lambda e: scroll_zoom(+1))    # old Linux
    root.bind("<Button-5>", lambda e: scroll_zoom(-1))    # old Linux

    # Pan (drag on the image)
    image_label.bind("<Button-1>", on_left_down)
    image_label.bind("<B1-Motion>", on_left_drag)
    image_label.bind("<ButtonRelease-1>", on_left_up)

    # Start at first file
    file_slider.set(0)
    load_current_file()

    root.mainloop()