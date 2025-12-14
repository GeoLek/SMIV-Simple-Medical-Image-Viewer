# viewer_multi_slicetime.py

import os
import tkinter as tk
from tkinter import ttk, BooleanVar, IntVar, Checkbutton, Scale, filedialog, messagebox
import nibabel as nib
import numpy as np
from PIL import Image, ImageTk
import image_loader
import image_processing
import overlay_utils

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
    root.geometry("1000x800")

    # --------------------------------------------------------
    # Viewer state
    # --------------------------------------------------------
    state = {
        "file_paths": file_paths,
        "current_file_index": 0,
        "current_file_type": None,
        "volume": None,  # either (H,W,3) RGB for PNG/TIFF, OR 4D (H,W,Z,T) for medical data
        "z_index": 0,
        "t_index": 0,
        "z_max": 1,
        "t_max": 1,
        "zoom_factor": 1.0,
        "zoom_enabled": False,
        # Pan / dragging state
        "pan_x": 0.0,
        "pan_y": 0.0,
        "dragging": False,
        "drag_start_x": 0,
        "drag_start_y": 0,
        "drag_start_pan_x": 0.0,
        "drag_start_pan_y": 0.0,
        "mask_path": None,
        "mask_volume": None,
        "overlay_enabled": False,
        "overlay_alpha": 35,  # 0..100
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
    info_label.pack(side=tk.TOP, pady=5)

    # Frame that will hold the image and expand with the window
    image_frame = tk.Frame(root, bg="black")
    image_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    image_label = tk.Label(image_frame, bg="black")
    image_label.pack(expand=True)

    # --- File navigation (Prev / Next + file slider)
    nav_frame = tk.Frame(root)
    nav_frame.pack(pady=10)

    def export_current_view():
        """
        Export exactly what is currently shown in the viewer as a PNG.
        We read the image back from image_label.image (the PhotoImage).
        """
        tk_img = getattr(image_label, "image", None)
        if tk_img is None:
            messagebox.showwarning("Export Current View", "No image is currently displayed to export.")
            return

        pil_img = ImageTk.getimage(tk_img)

        file_path = filedialog.asksaveasfilename(
            title="Save current view as PNG",
            defaultextension=".png",
            filetypes=[("PNG Image", "*.png")]
        )
        if not file_path:
            return

        try:
            pil_img.save(file_path, format="PNG")
            messagebox.showinfo("Export Current View", f"Image successfully saved to:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Export Current View", f"Failed to save image:\n{e}")

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

    export_button = tk.Button(
        preproc_frame,
        text="Export Current View as PNG",
        command=export_current_view
    )
    export_button.pack(anchor="w", pady=(5, 0))

    overlay_var = BooleanVar(value=False)
    alpha_var = IntVar(value=35)

    def toggle_overlay():
        state["overlay_enabled"] = overlay_var.get()
        display_current_slice()

    def on_alpha_change(val):
        state["overlay_alpha"] = int(float(val))
        display_current_slice()

    def load_mask_dialog():
        mask_path = filedialog.askopenfilename(
            title="Select segmentation mask",
            initialdir=".",
            filetypes=[
                ("Mask files", "*.nii *.nii.gz *.png *.jpg *.jpeg *.tif *.tiff *.npy"),
                ("All files", "*"),
            ],
        )
        if not mask_path:
            return

        try:
            m = overlay_utils.load_mask(mask_path)
        except Exception as e:
            messagebox.showerror("Load Mask", f"Failed to load mask:\n{e}")
            return

        state["mask_path"] = mask_path
        state["mask_volume"] = m
        state["overlay_enabled"] = True
        overlay_var.set(True)

        messagebox.showinfo("Load Mask", f"Mask loaded:\n{os.path.basename(mask_path)}")
        display_current_slice()

    mask_btn = tk.Button(preproc_frame, text="Load Mask", command=load_mask_dialog)
    mask_btn.pack(anchor="w", pady=(8, 0))

    Checkbutton(
        preproc_frame,
        text="Show Segmentation Overlay",
        variable=overlay_var,
        command=toggle_overlay
    ).pack(anchor="w")

    Scale(
        preproc_frame,
        from_=0,
        to=100,
        label="Overlay Alpha (%)",
        variable=alpha_var,
        orient=tk.HORIZONTAL,
        command=on_alpha_change
    ).pack(fill=tk.X)

    zoom_var = BooleanVar(value=False)

    def toggle_zoom():
        state["zoom_enabled"] = zoom_var.get()
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
        if not state["zoom_enabled"]:
            return
        step = 1.1
        if event.delta > 0:
            state["zoom_factor"] *= step
        else:
            state["zoom_factor"] /= step
        state["zoom_factor"] = max(0.5, min(10.0, state["zoom_factor"]))
        display_current_slice()

    def scroll_zoom(direction):
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
        if not state["zoom_enabled"]:
            return
        state["dragging"] = True
        state["drag_start_x"] = event.x
        state["drag_start_y"] = event.y
        state["drag_start_pan_x"] = state["pan_x"]
        state["drag_start_pan_y"] = state["pan_y"]

    def on_left_up(event):
        state["dragging"] = False

    def on_left_drag(event):
        if not state["dragging"] or not state["zoom_enabled"]:
            return

        dx = event.x - state["drag_start_x"]
        dy = event.y - state["drag_start_y"]

        zf = state["zoom_factor"] if state["zoom_factor"] != 0 else 1.0
        state["pan_x"] = state["drag_start_pan_x"] - dx / zf
        state["pan_y"] = state["drag_start_pan_y"] - dy / zf

        display_current_slice()

    # --------------------------------------------------------
    # Display helpers
    # --------------------------------------------------------
    def build_display_image():
        vol = state["volume"]
        if vol is None:
            return None

        file_type = state.get("current_file_type")
        is_rgb_2d = (
            file_type in ["JPEG/PNG", "TIFF"]
            and vol.ndim == 3
            and vol.shape[2] == 3
        )

        # Extract slice
        if is_rgb_2d:
            slice_2d = vol.astype(np.float32)
        else:
            slice_2d = vol[..., state["z_index"], state["t_index"]].astype(np.float32)
            # Normalize medical slice to [0..255]
            min_val, max_val = slice_2d.min(), slice_2d.max()
            if max_val != min_val:
                slice_2d = (slice_2d - min_val) / (max_val - min_val) * 255.0

        # Apply preprocessing
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

        # Fit to window
        frame_width = image_frame.winfo_width()
        frame_height = image_frame.winfo_height()

        h, w = out.shape[:2]
        if frame_width <= 1 or frame_height <= 1:
            new_w, new_h = w, h
        else:
            max_display_width = max(100, frame_width - 10)
            max_display_height = max(100, frame_height - 10)
            scale = min(max_display_width / float(w), max_display_height / float(h))
            if scale <= 0:
                scale = 1.0
            new_w = max(1, int(w * scale))
            new_h = max(1, int(h * scale))

        # Convert to PIL
        if out.ndim == 2:
            pil_img = Image.fromarray(out, mode="L")
        else:
            # If colormap was applied to a grayscale image, OpenCV output is BGR
            colormap_applied = settings["colormap"].get() and (not is_rgb_2d)
            if colormap_applied:
                pil_img = Image.fromarray(out[..., ::-1], mode="RGB")  # BGR->RGB
            else:
                pil_img = Image.fromarray(out, mode="RGB")  # already RGB

        if (new_w, new_h) != (w, h):
            pil_img = pil_img.resize((new_w, new_h), resample=Image.BILINEAR)

        # Apply segmentation overlay (if enabled and mask loaded)
        if state.get("overlay_enabled") and state.get("mask_volume") is not None:
            try:
                m2d = overlay_utils.get_mask_slice(
                    state["mask_volume"],
                    z_index=state.get("z_index", 0),
                    t_index=state.get("t_index", 0),
                )
                m2d = overlay_utils.to_binary_mask(m2d, threshold=0.0)

                # image slice size BEFORE window resizing
                img_h, img_w = slice_2d.shape[:2]  # this is the pre-zoom slice size

                if m2d.shape != (img_h, img_w):
                    m2d = overlay_utils.resize_mask_nearest(m2d, img_w, img_h)

                m2d = image_processing.apply_zoom_and_pan_mask(
                    m2d,
                    zoom_factor=state["zoom_factor"],
                    pan_x=state["pan_x"],
                    pan_y=state["pan_y"],
                )

                # Resize mask to match the final displayed image size
                target_w, target_h = pil_img.size
                m2d = overlay_utils.resize_mask_nearest(m2d, target_w, target_h)

                alpha = float(state.get("overlay_alpha", 35)) / 100.0
                pil_img = overlay_utils.apply_overlay_to_pil(
                    pil_img,
                    m2d,
                    alpha=alpha,
                    color_rgb=(255, 0, 0),
                )
            except Exception as e:
                # Do not crash viewer if mask doesn't match; just show base image
                print("[WARN] Overlay failed:", e)

        return pil_img

    def display_current_slice():
        pil_img = build_display_image()
        if pil_img is None:
            image_label.config(image="", text="Cannot display file", compound=tk.CENTER)
            return

        tk_img = ImageTk.PhotoImage(pil_img)
        image_label.config(image=tk_img, text="", compound=tk.NONE)
        image_label.image = tk_img

    # --------------------------------------------------------
    # Loading
    # --------------------------------------------------------
    def load_current_file():
        idx = state["current_file_index"]
        path = file_paths[idx]
        file_type, meta_str = image_loader.detect_file_type_and_metadata(path)
        state["current_file_type"] = file_type

        info_label.config(text=f"[{idx+1}/{len(file_paths)}] {os.path.basename(path)} - {file_type or 'Unknown'}")
        metadata_label.config(text=meta_str)

        arr = None
        if file_type == "DICOM":
            arr = image_loader.load_dicom(path)
        elif file_type == "NIfTI":
            arr = nib.load(path).get_fdata()
        elif file_type == "JPEG/PNG":
            arr = image_loader.load_jpeg_png(path)
        elif file_type == "TIFF":
            arr = image_loader.load_tiff(path)
        elif file_type == "WHOLESLIDE":
            arr = image_loader.load_whole_slide_downsampled(path)

        # Store volume properly
        if arr is None:
            state["volume"] = None
        else:
            is_rgb_2d = (
                file_type in ["JPEG/PNG", "TIFF"]
                and arr.ndim == 3
                and arr.shape[2] == 3
            )

            if is_rgb_2d:
                state["volume"] = arr  # (H, W, 3)
            else:
                # force to 4D (H,W,Z,T)
                if arr.ndim == 2:
                    arr = arr[..., np.newaxis, np.newaxis]
                elif arr.ndim == 3:
                    arr = arr[..., np.newaxis]
                state["volume"] = arr

        # Configure sliders
        if state["volume"] is None:
            state["z_max"] = 1
            state["t_max"] = 1
            z_slider.pack_forget()
            t_slider.pack_forget()
        else:
            vol_shape = state["volume"].shape
            is_rgb_2d = (
                file_type in ["JPEG/PNG", "TIFF"]
                and len(vol_shape) == 3
                and vol_shape[2] == 3
            )

            if is_rgb_2d:
                state["z_max"] = 1
                state["t_max"] = 1
                state["z_index"] = 0
                state["t_index"] = 0
                z_slider.pack_forget()
                t_slider.pack_forget()
            else:
                state["z_max"] = vol_shape[2]
                state["t_max"] = vol_shape[3]
                state["z_index"] = min(state["z_max"] // 2, state["z_max"] - 1)
                state["t_index"] = min(state["t_max"] // 2, state["t_max"] - 1)

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

        # Reset zoom/pan
        state["zoom_factor"] = 1.0
        state["pan_x"] = 0.0
        state["pan_y"] = 0.0

        display_current_slice()

    # Throttle resize-triggered redraws to avoid flicker & callback storms
    resize_pending = {"flag": False}

    def on_root_resize(event):
        if event.widget is not root:
            return
        if resize_pending["flag"]:
            return
        resize_pending["flag"] = True

        def do_redraw():
            resize_pending["flag"] = False
            try:
                display_current_slice()
            except Exception as e:
                print("[ERROR] Exception during display_current_slice on resize:", e)

        root.after(60, do_redraw)

    root.bind("<Configure>", on_root_resize)

    # --------------------------------------------------------
    # Bind events and initialize
    # --------------------------------------------------------
    root.bind("<MouseWheel>", on_mouse_wheel)
    root.bind("<Button-4>", lambda e: scroll_zoom(+1))
    root.bind("<Button-5>", lambda e: scroll_zoom(-1))

    image_label.bind("<Button-1>", on_left_down)
    image_label.bind("<B1-Motion>", on_left_drag)
    image_label.bind("<ButtonRelease-1>", on_left_up)

    file_slider.set(0)
    load_current_file()

    root.mainloop()
