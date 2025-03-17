# viewer_multi_slicetime.py

import tkinter as tk
from tkinter import ttk
import os
import numpy as np
import nibabel as nib
import image_loader
from PIL import Image, ImageTk

def create_viewer(file_paths, modality=""):
    """
    Single window to navigate multiple files (Next/Prev)
    and also multiple slices (Z-slice) + time (T-slice) if 3D/4D.
    """
    root = tk.Toplevel()
    root.title("Multi-File, Multi-Slice/Time Viewer")

    state = {
        "file_paths": file_paths,
        "current_file_index": 0,
        "volume": None,       # 3D/4D volume data
        "z_index": 0,         # slice index
        "t_index": 0,         # time index for 4D
        "z_max": 0,
        "t_max": 0,
    }

    # Info label: shows current file and type
    info_label = tk.Label(root, text="", font=("Arial", 14))
    info_label.pack(pady=5)

    # Canvas/Label to show the slice
    image_label = tk.Label(root)
    image_label.pack()

    # Navigation for files
    nav_frame = tk.Frame(root)
    nav_frame.pack(pady=10)

    btn_prev = tk.Button(nav_frame, text="<< Prev File", command=lambda: change_file(-1))
    btn_prev.pack(side=tk.LEFT, padx=20)

    btn_next = tk.Button(nav_frame, text="Next File >>", command=lambda: change_file(+1))
    btn_next.pack(side=tk.LEFT, padx=20)

    # Slicers for Z and T
    z_slider = ttk.Scale(root, from_=0, to=0, orient="horizontal", command=lambda v: update_z(int(float(v))))
    z_slider.pack(fill=tk.X, padx=10, pady=5)

    t_slider = ttk.Scale(root, from_=0, to=0, orient="horizontal", command=lambda v: update_t(int(float(v))))
    t_slider.pack(fill=tk.X, padx=10, pady=5)

    def change_file(delta):
        """ Switch to next/prev file """
        state["current_file_index"] += delta
        if state["current_file_index"] < 0:
            state["current_file_index"] = len(file_paths) - 1
        elif state["current_file_index"] >= len(file_paths):
            state["current_file_index"] = 0
        load_current_file()

    def update_z(z_idx):
        state["z_index"] = z_idx
        display_current_slice()

    def update_t(t_idx):
        state["t_index"] = t_idx
        display_current_slice()

    def load_current_file():
        """ Load the selected file into state["volume"] + set up sliders """
        idx = state["current_file_index"]
        path = file_paths[idx]
        file_type, _ = image_loader.detect_file_type_and_metadata(path)

        info_label.config(text=f"[{idx+1}/{len(file_paths)}] {os.path.basename(path)} - {file_type or '??'}")

        if file_type == "DICOM":
            arr = image_loader.load_dicom(path)
            # If multi-frame DICOM => shape could be (Height, Width, Frames)
            # If 2D => shape is (H, W)
            # If 3D => shape is (H, W, Slices)
            if arr.ndim == 2:
                # Treat as 2D => expand dims
                arr = arr[..., np.newaxis, np.newaxis]  # shape => (H, W, 1, 1)
            elif arr.ndim == 3:
                # shape => (H, W, frames) => interpret as (H, W, Z) or (H, W, Z, T=1)
                arr = arr[..., np.newaxis]  # shape => (H, W, Z, 1)
            state["volume"] = arr

        elif file_type == "NIfTI":
            vol = nib.load(path).get_fdata()
            # vol can be 2D, 3D, or 4D
            if vol.ndim == 2:
                vol = vol[..., np.newaxis, np.newaxis]  # shape => (H, W, 1, 1)
            elif vol.ndim == 3:
                vol = vol[..., np.newaxis]  # shape => (H, W, Z, 1)
            # shape => (H, W, Z, T)
            state["volume"] = vol
        elif file_type == "JPEG/PNG":
            arr = image_loader.load_jpeg_png(path)
            # shape => (H, W)
            arr = arr[..., np.newaxis, np.newaxis]  # shape => (H, W, 1, 1)
            state["volume"] = arr
        else:
            state["volume"] = None

        # Update shape info for Z/T
        if state["volume"] is not None:
            # shape => (H, W, Z, T)
            shape_4d = state["volume"].shape
            state["z_max"] = max(1, shape_4d[2])
            state["t_max"] = max(1, shape_4d[3])
            # Reset indexes
            state["z_index"] = state["z_max"] // 2 if state["z_max"] > 1 else 0
            state["t_index"] = state["t_max"] // 2 if state["t_max"] > 1 else 0

            # Update Sliders
            z_slider.config(to=state["z_max"] - 1)
            t_slider.config(to=state["t_max"] - 1)

            z_slider.set(state["z_index"])
            t_slider.set(state["t_index"])

            # Hide slider if Z=1 or T=1
            if state["z_max"] <= 1:
                z_slider.pack_forget()
            else:
                z_slider.pack(fill=tk.X, padx=10, pady=5)

            if state["t_max"] <= 1:
                t_slider.pack_forget()
            else:
                t_slider.pack(fill=tk.X, padx=10, pady=5)

        display_current_slice()

    def display_current_slice():
        """ Display the slice at [z_index, t_index] """
        vol = state["volume"]
        if vol is None:
            image_label.config(image="", text="Cannot display file", compound=tk.CENTER)
            return

        z_i = state["z_index"]
        t_i = state["t_index"]
        # shape => (H, W, Z, T)
        slice_2d = vol[..., z_i, t_i]

        # Normalize to [0,255] for display
        slice_2d = slice_2d.astype(np.float32)
        min_val, max_val = slice_2d.min(), slice_2d.max()
        if max_val != min_val:
            slice_2d = (slice_2d - min_val) / (max_val - min_val) * 255
        slice_2d = slice_2d.astype(np.uint8)

        pil_img = Image.fromarray(slice_2d)
        tk_img = ImageTk.PhotoImage(pil_img)
        image_label.config(image=tk_img, text="", compound=tk.NONE)
        image_label.image = tk_img

    # Initialize with the first file
    load_current_file()
    root.mainloop()
