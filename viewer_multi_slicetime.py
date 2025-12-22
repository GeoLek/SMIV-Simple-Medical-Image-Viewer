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
import ui_theme
import json


def create_viewer(file_paths, modality=""):
    """
    Multi-file, multi-slice/time viewer with:
      - DICOM / NIfTI / PNG-JPG / TIFF / WHOLESLIDE
      - File slider + Prev/Next
      - Slice (Z) and time (T) sliders
      - Preprocessing: HistEq, Brightness/Contrast, Colormap
      - Zoom (mouse wheel) + Pan (left-drag)
      - Overlay: mask load/clear + alpha + outline + label visibility + label-map names
      - UI: PanedWindow (image left, toolbox right) + toolbox tabs
    """

    root = tk.Toplevel()
    root.title("Multi-File, Multi-Slice/Time Viewer (Zoom + Pan + Preprocessing + Overlay)")
    root.geometry("1200x800")

    # --------------------------------------------------------
    # Viewer state
    # --------------------------------------------------------
    state = {
        "file_paths": file_paths,
        "current_file_index": 0,
        "current_file_type": None,
        "volume": None,
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

        # Overlay state
        "mask_path": None,
        "mask_volume": None,
        "overlay_enabled": False,
        "overlay_alpha": 35,  # 0..100
        "overlay_label_colors": None,  # multiclass support
        "overlay_outline": False,  # outline mode
        "overlay_label_names": None,  # {int_label: "name"}
        "overlay_warned_mismatch": False,  # warn once per mask
        "overlay_label_visible": None,  # {label:int -> bool}
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
    # Root layout (grid): header, paned, status
    # --------------------------------------------------------
    root.grid_rowconfigure(1, weight=1)
    root.grid_columnconfigure(0, weight=1)

    info_label = tk.Label(root, font=("Arial", 14), anchor="w")
    info_label.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 4))

    main_pane = ttk.Panedwindow(root, orient=tk.HORIZONTAL)
    main_pane.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)

    # Left: image
    image_frame = tk.Frame(main_pane, bg="black")
    image_frame.pack_propagate(False)
    image_label = tk.Label(image_frame, bg="black")
    image_label.pack(expand=True, fill=tk.BOTH)

    # Right: toolbox
    toolbox_frame = tk.Frame(main_pane)
    toolbox_frame.pack_propagate(False)

    main_pane.add(image_frame, weight=3)
    main_pane.add(toolbox_frame, weight=1)

    status_label = tk.Label(root, font=("Arial", 11), anchor="w")
    status_label.grid(row=2, column=0, sticky="ew", padx=10, pady=(4, 8))

    # Apply theme to viewer (exclude the image area so it stays black)
    ui_theme.apply_viewer_theme(root, exclude_widgets=[image_frame, image_label])

    # --------------------------------------------------------
    # Toolbox tabs
    # --------------------------------------------------------
    notebook = ttk.Notebook(toolbox_frame)
    notebook.pack(fill=tk.BOTH, expand=True)

    tab_nav = tk.Frame(notebook)
    tab_preproc = tk.Frame(notebook)
    tab_overlay = tk.Frame(notebook)

    notebook.add(tab_nav, text="Navigation")
    notebook.add(tab_preproc, text="Preprocessing")
    notebook.add(tab_overlay, text="Overlay")

    # Make tabs match theme backgrounds (since they are tk.Frame)
    tab_nav.configure(bg=ui_theme.THEME["bg"])
    tab_preproc.configure(bg=ui_theme.THEME["bg"])
    tab_overlay.configure(bg=ui_theme.THEME["bg"])

    # --------------------------------------------------------
    # NAV TAB: file navigation + sliders + zoom
    # --------------------------------------------------------
    nav_frame = tk.Frame(tab_nav, bg=ui_theme.THEME["bg"])
    nav_frame.pack(fill=tk.X, padx=10, pady=(10, 5))

    btn_prev = tk.Button(nav_frame, text="<< Prev File")
    btn_prev.pack(side=tk.LEFT, padx=(0, 8))

    btn_next = tk.Button(nav_frame, text="Next File >>")
    btn_next.pack(side=tk.LEFT)

    file_slider = ttk.Scale(
        tab_nav,
        from_=0,
        to=max(0, len(file_paths) - 1),
        orient="horizontal",
    )
    file_slider.pack(fill=tk.X, padx=10, pady=(8, 10))

    z_slider = ttk.Scale(tab_nav, from_=0, to=0, orient="horizontal")
    t_slider = ttk.Scale(tab_nav, from_=0, to=0, orient="horizontal")

    # Slice/time sliders live in Navigation tab
    z_slider.pack(fill=tk.X, padx=10, pady=(5, 5))
    t_slider.pack(fill=tk.X, padx=10, pady=(5, 10))
    z_slider.pack_forget()
    t_slider.pack_forget()

    # Zoom controls
    zoom_var = BooleanVar(value=False)

    def toggle_zoom():
        state["zoom_enabled"] = zoom_var.get()
        state["pan_x"] = 0.0
        state["pan_y"] = 0.0
        state["zoom_factor"] = 1.0
        display_current_slice()

    Checkbutton(
        tab_nav,
        text="Enable Zoom (wheel) + Pan (drag)",
        variable=zoom_var,
        command=toggle_zoom
    ).pack(anchor="w", padx=10, pady=(0, 5))

    def reset_view():
        state["pan_x"] = 0.0
        state["pan_y"] = 0.0
        state["zoom_factor"] = 1.0
        display_current_slice()

    tk.Button(tab_nav, text="Reset Zoom/Pan", command=reset_view).pack(anchor="w", padx=10, pady=(0, 10))

    # Export button (Navigation tab feels right)
    def export_current_view():
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

    tk.Button(tab_nav, text="Export Current View as PNG", command=export_current_view).pack(
        anchor="w", padx=10, pady=(0, 10)
    )

    # --------------------------------------------------------
    # PREPROC TAB
    # --------------------------------------------------------
    preproc_frame = tk.Frame(tab_preproc, bg=ui_theme.THEME["bg"])
    preproc_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

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
    ).pack(fill=tk.X, pady=(5, 0))

    Scale(
        preproc_frame,
        from_=1,
        to=5,
        resolution=0.1,
        label="Contrast",
        variable=settings["contrast"],
        orient=tk.HORIZONTAL,
        command=lambda x: display_current_slice()
    ).pack(fill=tk.X, pady=(5, 0))

    # --------------------------------------------------------
    # OVERLAY TAB
    # --------------------------------------------------------
    overlay_frame = tk.Frame(tab_overlay, bg=ui_theme.THEME["bg"])
    overlay_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    legend_label = tk.Label(overlay_frame, text="", justify="left", anchor="w")
    legend_label.pack(fill=tk.X, pady=(0, 8))

    overlay_var = BooleanVar(value=False)
    alpha_var = IntVar(value=35)
    outline_var = BooleanVar(value=False)

    def refresh_legend():
        lc = state.get("overlay_label_colors") or {}
        names = state.get("overlay_label_names") or {}

        if state.get("mask_volume") is None:
            legend_label.config(text="")
            return

        if len(lc) == 0:
            legend_label.config(text="Overlay labels: (binary)")
            return

        lines = ["Overlay labels:"]
        for lbl, col in sorted(lc.items()):
            lbl_i = int(lbl)
            name = names.get(lbl_i)
            if name:
                lines.append(f"  Label {lbl_i} ({name}): RGB{tuple(col)}")
            else:
                lines.append(f"  Label {lbl_i}: RGB{tuple(col)}")
        legend_label.config(text="\n".join(lines))

    def toggle_overlay():
        state["overlay_enabled"] = overlay_var.get()
        display_current_slice()

    def on_alpha_change(val):
        v = int(float(val))
        state["overlay_alpha"] = v
        if alpha_var.get() != v:
            alpha_var.set(v)
        display_current_slice()

    def toggle_outline():
        state["overlay_outline"] = outline_var.get()
        display_current_slice()

    # Label visibility UI (scrollable list inside overlay tab)
    labels_outer = tk.Frame(overlay_frame, bg=ui_theme.THEME["bg"])
    labels_outer.pack(fill=tk.BOTH, expand=True, pady=(8, 8))

    labels_canvas = tk.Canvas(labels_outer, highlightthickness=0)
    labels_scroll = tk.Scrollbar(labels_outer, orient=tk.VERTICAL, command=labels_canvas.yview)
    labels_canvas.configure(yscrollcommand=labels_scroll.set)

    labels_scroll.pack(side=tk.RIGHT, fill=tk.Y)
    labels_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    labels_frame = tk.Frame(labels_canvas, bg=ui_theme.THEME["bg"])
    labels_canvas.create_window((0, 0), window=labels_frame, anchor="nw")

    def _sync_labels_scrollregion(_event=None):
        labels_canvas.configure(scrollregion=labels_canvas.bbox("all"))

    labels_frame.bind("<Configure>", _sync_labels_scrollregion)

    def _labels_mousewheel(event):
        # Windows/macOS delta
        if hasattr(event, "delta") and event.delta:
            labels_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        else:
            # Linux Button-4/5
            if event.num == 4:
                labels_canvas.yview_scroll(-3, "units")
            elif event.num == 5:
                labels_canvas.yview_scroll(3, "units")

    def _bind_labels_wheel(_e=None):
        labels_canvas.bind_all("<MouseWheel>", _labels_mousewheel)
        labels_canvas.bind_all("<Button-4>", _labels_mousewheel)
        labels_canvas.bind_all("<Button-5>", _labels_mousewheel)

    def _unbind_labels_wheel(_e=None):
        labels_canvas.unbind_all("<MouseWheel>")
        labels_canvas.unbind_all("<Button-4>")
        labels_canvas.unbind_all("<Button-5>")

    labels_canvas.bind("<Enter>", _bind_labels_wheel)
    labels_canvas.bind("<Leave>", _unbind_labels_wheel)

    label_vars = {}  # local dict: lbl -> BooleanVar

    def on_label_visibility_change(lbl_i):
        vis = state.get("overlay_label_visible") or {}
        v = label_vars.get(lbl_i)
        if v is None:
            return
        vis[int(lbl_i)] = bool(v.get())
        state["overlay_label_visible"] = vis
        display_current_slice()

    def rebuild_label_checkboxes():
        for w in labels_frame.winfo_children():
            w.destroy()
        label_vars.clear()

        lc = state.get("overlay_label_colors") or {}
        vis = state.get("overlay_label_visible") or {}
        names = state.get("overlay_label_names") or {}

        if len(lc) == 0:
            return

        tk.Label(labels_frame, text="Visible labels:", anchor="w").pack(anchor="w")

        for lbl in sorted(lc.keys()):
            lbl_i = int(lbl)
            v = BooleanVar(value=bool(vis.get(lbl_i, True)))
            label_vars[lbl_i] = v

            name = names.get(lbl_i)
            if name:
                txt = f"Label {lbl_i} ({name})"
            else:
                txt = f"Label {lbl_i}"

            cb = Checkbutton(
                labels_frame,
                text=txt,
                variable=v,
                command=(lambda lid=lbl_i: on_label_visibility_change(lid))
            )
            cb.pack(anchor="w")

        ui_theme.apply_viewer_theme(root, exclude_widgets=[image_frame, image_label])
        _sync_labels_scrollregion()

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
        state["overlay_warned_mismatch"] = False  # reset warning per mask

        state["overlay_label_colors"] = overlay_utils.default_label_colormap(m)
        lc = state["overlay_label_colors"] or {}
        state["overlay_label_visible"] = {int(lbl): True for lbl in lc.keys()}

        # Auto-load sidecar label names (optional)
        state["overlay_label_names"] = overlay_utils.load_label_names_for_mask(mask_path)

        overlay_var.set(True)
        alpha_var.set(state["overlay_alpha"])
        outline_var.set(state["overlay_outline"])

        messagebox.showinfo("Load Mask", f"Mask loaded:\n{os.path.basename(mask_path)}")
        refresh_legend()
        rebuild_label_checkboxes()
        display_current_slice()

    def clear_mask():
        state["mask_path"] = None
        state["mask_volume"] = None
        state["overlay_label_colors"] = None
        state["overlay_label_names"] = None
        state["overlay_label_visible"] = None
        state["overlay_enabled"] = False
        overlay_var.set(False)
        refresh_legend()
        rebuild_label_checkboxes()
        display_current_slice()

    def load_labelmap_dialog():
        """
        Load a label-map JSON file mapping label integers to names.
        Supported JSON formats:
          A) {"1": "liver", "2": "pancreas"}
          B) {"labels": {"1": "liver", "2": "pancreas"}}
        """
        path = filedialog.askopenfilename(
            title="Select label-map JSON",
            initialdir=".",
            filetypes=[("JSON files", "*.json"), ("All files", "*")],
        )
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, dict) and "labels" in data and isinstance(data["labels"], dict):
                data = data["labels"]

            if not isinstance(data, dict):
                raise ValueError("Label-map JSON must be a dict or contain a 'labels' dict.")

            out = {}
            for k, v in data.items():
                try:
                    kk = int(k)
                except Exception:
                    continue
                if isinstance(v, str) and v.strip():
                    out[kk] = v.strip()

            state["overlay_label_names"] = out
            messagebox.showinfo("Label-map", f"Loaded {len(out)} label names.")
            refresh_legend()
            rebuild_label_checkboxes()
            display_current_slice()

        except Exception as e:
            messagebox.showerror("Label-map", f"Failed to load label-map:\n{e}")

    # Overlay controls (top of overlay tab)
    tk.Button(overlay_frame, text="Load Mask", command=load_mask_dialog).pack(anchor="w")
    tk.Button(overlay_frame, text="Clear Mask", command=clear_mask).pack(anchor="w", pady=(2, 8))
    tk.Button(overlay_frame, text="Load Label-Map (JSON)", command=load_labelmap_dialog).pack(anchor="w", pady=(0, 8))

    Checkbutton(
        overlay_frame,
        text="Show Segmentation Overlay",
        variable=overlay_var,
        command=toggle_overlay
    ).pack(anchor="w")

    Checkbutton(
        overlay_frame,
        text="Overlay Outline Only",
        variable=outline_var,
        command=toggle_outline
    ).pack(anchor="w", pady=(2, 6))

    Scale(
        overlay_frame,
        from_=0,
        to=100,
        label="Overlay Alpha (%)",
        variable=alpha_var,
        orient=tk.HORIZONTAL,
        command=on_alpha_change
    ).pack(fill=tk.X, pady=(0, 8))

    # --------------------------------------------------------
    # Metadata window
    # --------------------------------------------------------
    metadata_win = tk.Toplevel(root)
    metadata_win.title("File Metadata")
    metadata_label = tk.Label(metadata_win, font=("Arial", 12), justify="left", anchor="w")
    metadata_label.pack(padx=10, pady=10)
    ui_theme.apply_viewer_theme(metadata_win)

    # --------------------------------------------------------
    # Helpers
    # --------------------------------------------------------
    def update_status():
        parts = []
        parts.append(f"File {state['current_file_index'] + 1}/{len(file_paths)}")
        ft = state.get("current_file_type") or "Unknown"
        parts.append(ft)

        if state["volume"] is not None:
            if ft not in ["JPEG/PNG", "TIFF"]:
                parts.append(f"Z {state['z_index'] + 1}/{max(1, state['z_max'])}")
                parts.append(f"T {state['t_index'] + 1}/{max(1, state['t_max'])}")

        if state.get("zoom_enabled"):
            parts.append(f"Zoom {state.get('zoom_factor', 1.0):.2f}")

        if state.get("overlay_enabled") and state.get("mask_volume") is not None:
            parts.append(f"Overlay {state.get('overlay_alpha', 35)}%")

        status_label.config(text=" | ".join(parts))

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

    def on_left_up(_event):
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

        ft = state["current_file_type"]
        is_rgb = (
            ft in ["JPEG/PNG", "TIFF"]
            and vol.ndim == 3
            and vol.shape[2] == 3
        )

        if is_rgb:
            slice_2d = vol.astype(np.float32)
        else:
            slice_2d = vol[..., state["z_index"], state["t_index"]].astype(np.float32)
            mn, mx = slice_2d.min(), slice_2d.max()
            if mx > mn:
                slice_2d = (slice_2d - mn) / (mx - mn) * 255.0

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

        # Fit to available image_frame size
        h, w = out.shape[:2]
        fw = max(1, image_frame.winfo_width() - 10)
        fh = max(1, image_frame.winfo_height() - 10)
        scale = min(fw / w, fh / h) if fw > 1 and fh > 1 else 1.0
        new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))

        # Convert to PIL
        if out.ndim == 2:
            pil = Image.fromarray(out, "L")
        else:
            pil = Image.fromarray(out[..., ::-1] if settings["colormap"].get() and not is_rgb else out, "RGB")

        if (new_w, new_h) != (w, h):
            pil = pil.resize((new_w, new_h), Image.BILINEAR)

        # ---- Overlay ----
        if state["overlay_enabled"] and state["mask_volume"] is not None:
            m = overlay_utils.get_mask_slice(
                state["mask_volume"], state["z_index"], state["t_index"]
            )

            m = np.nan_to_num(m)
            m = np.rint(m).astype(np.int32)

            mh, mw = m.shape[:2]
            if (mw != w or mh != h) and not state.get("overlay_warned_mismatch", False):
                state["overlay_warned_mismatch"] = True
                print(f"[WARN] Mask shape {mw}x{mh} != image slice {w}x{h}. Resizing mask to match.")

            m = overlay_utils.resize_mask_nearest(m, w, h)
            m = image_processing.apply_zoom_and_pan_mask(
                m, state["zoom_factor"], state["pan_x"], state["pan_y"]
            )
            m = overlay_utils.resize_mask_nearest(m, new_w, new_h)
            m = m.astype(np.int32)

            alpha = float(state.get("overlay_alpha", 35)) / 100.0

            if state["overlay_label_colors"] is None:
                m_bin = overlay_utils.to_binary_mask(m)
                pil = overlay_utils.apply_overlay_to_pil(pil, m_bin, alpha)
            else:
                # Safe call: if your overlay_utils supports label_visible, use it; else fallback.
                try:
                    pil = overlay_utils.apply_multiclass_overlay_to_pil(
                        pil, m,
                        label_colors=state["overlay_label_colors"],
                        alpha=alpha,
                        outline=state["overlay_outline"],
                        label_visible=state.get("overlay_label_visible"),
                    )
                except TypeError:
                    pil = overlay_utils.apply_multiclass_overlay_to_pil(
                        pil, m,
                        label_colors=state["overlay_label_colors"],
                        alpha=alpha,
                        outline=state["overlay_outline"],
                    )

        return pil

    def display_current_slice():
        pil_img = build_display_image()
        if pil_img is None:
            image_label.config(image="", text="Cannot display file", compound=tk.CENTER)
            update_status()
            return

        tk_img = ImageTk.PhotoImage(pil_img)
        image_label.config(image=tk_img, text="", compound=tk.NONE)
        image_label.image = tk_img
        update_status()

    # --------------------------------------------------------
    # Loading
    # --------------------------------------------------------
    def on_file_slider(val):
        idx = int(float(val))
        state["current_file_index"] = idx
        load_current_file()

    file_slider.configure(command=on_file_slider)

    def change_file(delta):
        new_idx = (state["current_file_index"] + delta) % len(file_paths)
        state["current_file_index"] = new_idx
        file_slider.set(new_idx)
        load_current_file()

    btn_prev.configure(command=lambda: change_file(-1))
    btn_next.configure(command=lambda: change_file(+1))

    def on_z_change(val):
        state["z_index"] = int(float(val))
        display_current_slice()

    def on_t_change(val):
        state["t_index"] = int(float(val))
        display_current_slice()

    z_slider.configure(command=on_z_change)
    t_slider.configure(command=on_t_change)

    def load_current_file():
        idx = state["current_file_index"]
        path = file_paths[idx]
        file_type, meta_str = image_loader.detect_file_type_and_metadata(path)
        state["current_file_type"] = file_type

        info_label.config(text=f"[{idx + 1}/{len(file_paths)}] {os.path.basename(path)} - {file_type or 'Unknown'}")
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
            state["z_index"] = 0
            state["t_index"] = 0
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
                    z_slider.configure(to=state["z_max"] - 1)
                    z_slider.set(state["z_index"])
                    if not z_slider.winfo_ismapped():
                        z_slider.pack(fill=tk.X, padx=10, pady=(5, 5))
                else:
                    z_slider.pack_forget()

                if state["t_max"] > 1:
                    t_slider.configure(to=state["t_max"] - 1)
                    t_slider.set(state["t_index"])
                    if not t_slider.winfo_ismapped():
                        t_slider.pack(fill=tk.X, padx=10, pady=(5, 10))
                else:
                    t_slider.pack_forget()

        # Reset zoom/pan on file change
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

    # Bind wheel for zoom globally
    root.bind("<MouseWheel>", on_mouse_wheel)
    root.bind("<Button-4>", lambda e: scroll_zoom(+1))
    root.bind("<Button-5>", lambda e: scroll_zoom(-1))

    # Pan events on image
    image_label.bind("<Button-1>", on_left_down)
    image_label.bind("<B1-Motion>", on_left_drag)
    image_label.bind("<ButtonRelease-1>", on_left_up)

    # Init
    file_slider.set(0)
    load_current_file()

    # Give image pane more space initially
    root.after(200, lambda: main_pane.sashpos(0, int(root.winfo_width() * 0.72)))

    root.mainloop()
