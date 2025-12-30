# viewer_multi_slicetime.py

import os
from pathlib import Path
import json
import tkinter as tk
from tkinter import ttk, BooleanVar, IntVar, Checkbutton, Scale, filedialog, messagebox

import nibabel as nib
import numpy as np
from PIL import Image, ImageTk

import image_loader
import image_processing
import overlay_utils
import ui_theme


class CollapsibleSection(tk.Frame):
    def __init__(self, parent, title, theme=None, open_by_default=False):
        super().__init__(parent, bg=(theme["bg"] if theme else None))

        self._theme = theme
        self._open = open_by_default

        header_bg = theme["header"] if theme else None
        header_fg = theme["header_text"] if theme else None

        self._btn = tk.Button(
            self,
            text=("▾ " if self._open else "▸ ") + title,
            anchor="w",
            relief="flat",
            bg=header_bg,
            fg=header_fg,
            activebackground=header_bg,
            activeforeground=header_fg,
            command=self.toggle,
        )
        self._btn.pack(fill=tk.X)

        self.content = tk.Frame(self, bg=(theme["bg"] if theme else None))
        if self._open:
            self.content.pack(fill=tk.X, pady=(4, 8))

    def toggle(self):
        self._open = not self._open
        txt = self._btn.cget("text")
        title = txt[2:] if len(txt) > 2 else txt
        self._btn.config(text=("▾ " if self._open else "▸ ") + title)

        if self._open:
            self.content.pack(fill=tk.X, pady=(4, 8))
        else:
            self.content.pack_forget()


def _safe_apply_viewer_theme(root, theme, exclude_widgets=None):
    exclude_widgets = set(exclude_widgets or [])

    def _apply_to_widget(w):
        if w in exclude_widgets:
            return

        cls = w.winfo_class()

        if cls in ("Frame", "Labelframe", "Toplevel"):
            try:
                w.configure(bg=theme["bg"])
            except Exception:
                pass
        elif cls == "Label":
            try:
                w.configure(bg=theme["bg"], fg=theme["text"])
            except Exception:
                pass
        elif cls == "Button":
            try:
                w.configure(
                    bg=theme["button"],
                    fg=theme["text"],
                    activebackground=theme["button_hover"],
                    activeforeground="black",
                )
            except Exception:
                pass
        elif cls == "Checkbutton":
            try:
                w.configure(
                    bg=theme["bg"],
                    fg=theme["text"],
                    activebackground=theme["bg"],
                    selectcolor=theme["bg"],
                )
            except Exception:
                pass
        elif cls == "Scale":
            try:
                w.configure(bg=theme["bg"], fg=theme["text"], highlightbackground=theme["bg"])
            except Exception:
                pass
        elif cls == "Canvas":
            try:
                w.configure(bg=theme["bg"])
            except Exception:
                pass

        for child in w.winfo_children():
            _apply_to_widget(child)

    try:
        root.configure(bg=theme["bg"])
    except Exception:
        pass

    _apply_to_widget(root)

    try:
        style = ttk.Style()
        style.configure("TNotebook", background=theme["bg"])
        style.configure("TNotebook.Tab", padding=(10, 6))
    except Exception:
        pass


def _config_dir() -> Path:
    d = Path.home() / ".smiv"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _presets_path() -> Path:
    return _config_dir() / "session_presets.json"


def _load_presets() -> dict:
    p = _presets_path()
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_presets(presets: dict) -> None:
    p = _presets_path()
    p.write_text(json.dumps(presets, indent=2), encoding="utf-8")


def _preset_key(path: str) -> str:
    return os.path.abspath(path)


def create_viewer(file_paths, modality="AUTO"):
    root = tk.Toplevel()
    root.title("SMIV Viewer")
    root.geometry("1200x800")

    theme = ui_theme.THEME

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
        "overlay_alpha": 35,
        "overlay_label_colors": None,
        "overlay_outline": False,
        "overlay_label_names": None,
        "overlay_warned_mismatch": False,
        "overlay_label_visible": None,

        "inspector_text": "",
        "last_disp_out": None,
        "last_disp_base_wh": None,
        "last_disp_scaled_wh": None,
        "last_mask_scaled": None,

        "dicom_meta": None,
        "is_ct": False
    }

    settings = {
        "hist_eq": BooleanVar(value=False),
        "colormap": BooleanVar(value=False),
        "brightness_contrast": BooleanVar(value=False),
        "brightness": IntVar(value=0),
        "contrast": IntVar(value=1),

        # CT Window/Level (applied before 0..255 conversion)
        "wl_enabled": BooleanVar(value=False),
        "wl_center": IntVar(value=40),
        "wl_width": IntVar(value=400),
    }

    WL_PRESETS_CT = {
        "Soft tissue": (40, 400),
        "Lung": (-600, 1500),
        "Bone": (300, 2000),
    }

    def auto_window_level_from_slice(slice_raw: np.ndarray):
        """
        Compute a robust auto window/level from the current slice.
        Uses percentiles so it's stable even with outliers.
        """
        x = slice_raw.astype(np.float32, copy=False)
        x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)

        # Avoid empty/constant slices
        if x.size == 0:
            return 40, 400

        # Robust range
        p1 = float(np.percentile(x, 1))
        p99 = float(np.percentile(x, 99))

        if p99 <= p1:
            mn = float(np.min(x))
            mx = float(np.max(x))
            if mx <= mn:
                return 40, 400
            p1, p99 = mn, mx

        width = max(1.0, p99 - p1)
        center = (p99 + p1) / 2.0
        return int(round(center)), int(round(width))

    root.grid_rowconfigure(1, weight=1)
    root.grid_columnconfigure(0, weight=1)

    # Header row (info only)
    info_label = tk.Label(root, font=("Arial", 14), anchor="w")
    info_label.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 4))

    main_pane = ttk.Panedwindow(root, orient=tk.HORIZONTAL)
    main_pane.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)

    image_frame = tk.Frame(main_pane, bg="black")
    image_frame.pack_propagate(False)
    image_label = tk.Label(image_frame, bg="black")
    image_label.pack(expand=True, fill=tk.BOTH)

    toolbox_frame = tk.Frame(main_pane)
    toolbox_frame.pack_propagate(False)

    main_pane.add(image_frame, weight=3)
    main_pane.add(toolbox_frame, weight=1)

    # Status bar row with Quick Actions at bottom-right
    status_bar = tk.Frame(root)
    status_bar.grid(row=2, column=0, sticky="ew", padx=10, pady=(4, 8))
    status_bar.grid_columnconfigure(0, weight=1)

    status_label = tk.Label(status_bar, font=ui_theme.FONTS.get("status", ("Arial", 9)), anchor="w")
    status_label.grid(row=0, column=0, sticky="ew")

    quick_actions = tk.Frame(status_bar)
    quick_actions.grid(row=0, column=1, sticky="e")

    notebook = ttk.Notebook(toolbox_frame)
    notebook.pack(fill=tk.BOTH, expand=True)

    tab_nav = tk.Frame(notebook)
    tab_preproc = tk.Frame(notebook)
    tab_overlay = tk.Frame(notebook)

    notebook.add(tab_nav, text="Navigation")
    notebook.add(tab_preproc, text="Preprocessing")
    notebook.add(tab_overlay, text="Overlay")

    tab_nav.configure(bg=theme["bg"])
    tab_preproc.configure(bg=theme["bg"])
    tab_overlay.configure(bg=theme["bg"])

    def _confirm(title: str, msg: str) -> bool:
        return messagebox.askyesno(title, msg, parent=root)

    # NAV TAB
    nav_frame = tk.Frame(tab_nav, bg=theme["bg"])
    nav_frame.pack(fill=tk.X, padx=10, pady=(10, 5))

    btn_prev = tk.Button(nav_frame, text="<< Prev File")
    btn_prev.pack(side=tk.LEFT, padx=(0, 8))

    btn_next = tk.Button(nav_frame, text="Next File >>")
    btn_next.pack(side=tk.LEFT)

    file_slider = ttk.Scale(tab_nav, from_=0, to=max(0, len(file_paths) - 1), orient="horizontal")
    file_slider.pack(fill=tk.X, padx=10, pady=(8, 10))

    z_slider = ttk.Scale(tab_nav, from_=0, to=0, orient="horizontal")
    t_slider = ttk.Scale(tab_nav, from_=0, to=0, orient="horizontal")

    z_slider.pack(fill=tk.X, padx=10, pady=(5, 5))
    t_slider.pack(fill=tk.X, padx=10, pady=(5, 10))
    z_slider.pack_forget()
    t_slider.pack_forget()

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
        command=toggle_zoom,
        bg=theme["bg"],
        fg=theme["text"],
        activebackground=theme["bg"],
        selectcolor=theme["bg"],
    ).pack(anchor="w", padx=10, pady=(0, 5))

    def reset_view():
        state["pan_x"] = 0.0
        state["pan_y"] = 0.0
        state["zoom_factor"] = 1.0
        display_current_slice()

    def confirm_reset_view():
        if _confirm("Reset View", "Reset zoom and pan?"):
            reset_view()

    def export_current_view():
        tk_img = getattr(image_label, "image", None)
        if tk_img is None:
            messagebox.showwarning("Export Current View", "No image is currently displayed to export.", parent=root)
            return

        pil_img = ImageTk.getimage(tk_img)

        path = filedialog.asksaveasfilename(
            title="Save current view as PNG",
            defaultextension=".png",
            filetypes=[("PNG Image", "*.png")],
        )
        if not path:
            return
        try:
            pil_img.save(path, format="PNG")
            messagebox.showinfo("Export Current View", f"Saved:\n{path}", parent=root)
        except Exception as e:
            messagebox.showerror("Export Current View", f"Failed:\n{e}", parent=root)

    tk.Button(tab_nav, text="Reset Zoom/Pan", command=reset_view).pack(anchor="w", padx=10, pady=(0, 10))
    tk.Button(tab_nav, text="Export Current View as PNG", command=export_current_view).pack(anchor="w", padx=10, pady=(0, 10))

    # PREPROC TAB
    preproc_frame = tk.Frame(tab_preproc, bg=theme["bg"])
    preproc_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    Checkbutton(
        preproc_frame,
        text="Histogram Equalization",
        variable=settings["hist_eq"],
        command=lambda: display_current_slice(),
        bg=theme["bg"],
        fg=theme["text"],
        activebackground=theme["bg"],
        selectcolor=theme["bg"],
    ).pack(anchor="w")

    Checkbutton(
        preproc_frame,
        text="Apply Colormap",
        variable=settings["colormap"],
        command=lambda: display_current_slice(),
        bg=theme["bg"],
        fg=theme["text"],
        activebackground=theme["bg"],
        selectcolor=theme["bg"],
    ).pack(anchor="w")

    Checkbutton(
        preproc_frame,
        text="Brightness/Contrast",
        variable=settings["brightness_contrast"],
        command=lambda: display_current_slice(),
        bg=theme["bg"],
        fg=theme["text"],
        activebackground=theme["bg"],
        selectcolor=theme["bg"],
    ).pack(anchor="w")

    Scale(
        preproc_frame,
        from_=-100,
        to=100,
        label="Brightness",
        variable=settings["brightness"],
        orient=tk.HORIZONTAL,
        command=lambda _x: display_current_slice(),
    ).pack(fill=tk.X, pady=(5, 0))

    Scale(
        preproc_frame,
        from_=1,
        to=5,
        resolution=0.1,
        label="Contrast",
        variable=settings["contrast"],
        orient=tk.HORIZONTAL,
        command=lambda _x: display_current_slice(),
    ).pack(fill=tk.X, pady=(5, 0))

    # --- Window/Level (WL) ---
    wl_frame = tk.LabelFrame(preproc_frame, text="Window / Level", bg=theme["bg"], fg=theme["text"])
    wl_frame.pack(fill=tk.X, pady=(12, 0))

    wl_enable_cb = tk.Checkbutton(
        wl_frame,
        text="Enable Window/Level",
        variable=settings["wl_enabled"],
        command=lambda: display_current_slice(),
        bg=theme["bg"],
        fg=theme["text"],
        activebackground=theme["bg"],
        selectcolor=theme["bg"],
    )
    wl_enable_cb.pack(anchor="w", pady=(4, 0))

    wl_center_scale = tk.Scale(
        wl_frame,
        from_=-2000,
        to=2000,
        label="Center (Level)",
        variable=settings["wl_center"],
        orient=tk.HORIZONTAL,
        command=lambda _x: display_current_slice(),
        bg=theme["bg"],
        fg=theme["text"],
        troughcolor=theme["button"],
        highlightbackground=theme["bg"],
    )
    wl_center_scale.pack(fill=tk.X, pady=(6, 0))

    wl_width_scale = tk.Scale(
        wl_frame,
        from_=1,
        to=4000,
        label="Width (Window)",
        variable=settings["wl_width"],
        orient=tk.HORIZONTAL,
        command=lambda _x: display_current_slice(),
        bg=theme["bg"],
        fg=theme["text"],
        troughcolor=theme["button"],
        highlightbackground=theme["bg"],
    )
    wl_width_scale.pack(fill=tk.X, pady=(6, 0))

    wl_btn_row = tk.Frame(wl_frame, bg=theme["bg"])
    wl_btn_row.pack(fill=tk.X, pady=(8, 4))

    def _apply_ct_preset(name: str):
        c, w = WL_PRESETS_CT[name]
        settings["wl_center"].set(int(c))
        settings["wl_width"].set(int(w))
        settings["wl_enabled"].set(True)
        display_current_slice()

    def _auto_wl_now():
        # Use current displayed slice (raw) by rebuilding slice from volume directly
        vol = state.get("volume")
        if vol is None:
            return
        ft = state.get("current_file_type")
        is_rgb = (ft in ["JPEG/PNG", "TIFF"] and vol.ndim == 3 and vol.shape[2] == 3)
        if is_rgb:
            return  # WL not meaningful for RGB

        slice_raw = vol[..., state["z_index"], state["t_index"]].astype(np.float32)
        c, w = auto_window_level_from_slice(slice_raw)
        settings["wl_center"].set(int(c))
        settings["wl_width"].set(int(w))
        settings["wl_enabled"].set(True)
        display_current_slice()

    tk.Button(wl_btn_row, text="Auto", command=_auto_wl_now).pack(side=tk.LEFT, padx=(0, 6))

    # CT presets (enabled only for CT; see enabling function below)
    btn_preset_soft = tk.Button(wl_btn_row, text="Soft tissue", command=lambda: _apply_ct_preset("Soft tissue"))
    btn_preset_lung = tk.Button(wl_btn_row, text="Lung", command=lambda: _apply_ct_preset("Lung"))
    btn_preset_bone = tk.Button(wl_btn_row, text="Bone", command=lambda: _apply_ct_preset("Bone"))

    btn_preset_soft.pack(side=tk.LEFT, padx=(0, 6))
    btn_preset_lung.pack(side=tk.LEFT, padx=(0, 6))
    btn_preset_bone.pack(side=tk.LEFT)

    def _update_wl_ui_enabled():
        """
        Enable Window/Level controls for any *grayscale* volume (DICOM, NIfTI, etc.).
        Disable only for RGB images (PNG/TIFF color).
        HU presets should remain CT-only (handled separately if you have preset buttons).
        """
        vol = state.get("volume")
        ft = state.get("current_file_type")

        # Detect RGB 2D images (not suitable for WL in this simple model)
        is_rgb = (
                ft in ["JPEG/PNG", "TIFF"]
                and vol is not None
                and getattr(vol, "ndim", 0) == 3
                and vol.shape[2] == 3
        )

        st = "disabled" if is_rgb else "normal"

        try:
            wl_enable_cb.configure(state=st)
            wl_center_scale.configure(state=st)
            wl_width_scale.configure(state=st)
        except Exception:
            pass

        # If RGB, force WL off so pipeline doesn't try to apply it
        if is_rgb:
            settings["wl_enabled"].set(False)

        # CT preset buttons should be CT-only (but WL sliders can work for any grayscale)
        st_ct = "normal" if (not is_rgb and bool(state.get("is_ct", False))) else "disabled"
        try:
            btn_preset_soft.configure(state=st_ct)
            btn_preset_lung.configure(state=st_ct)
            btn_preset_bone.configure(state=st_ct)
        except Exception:
            pass

    def reset_preprocessing():
        settings["hist_eq"].set(False)
        settings["colormap"].set(False)
        settings["brightness_contrast"].set(False)
        settings["brightness"].set(0)
        settings["contrast"].set(1)
        settings["wl_enabled"].set(False)
        settings["wl_center"].set(40)
        settings["wl_width"].set(400)
        display_current_slice()

    def confirm_reset_preproc():
        if _confirm("Reset Preprocessing", "Reset all preprocessing settings to defaults?"):
            reset_preprocessing()

    tk.Button(preproc_frame, text="Reset Preprocessing", command=reset_preprocessing).pack(anchor="w", pady=(10, 0))

    # OVERLAY TAB
    overlay_frame = tk.Frame(tab_overlay, bg=theme["bg"])
    overlay_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    legend_label = tk.Label(overlay_frame, text="", justify="left", anchor="w")
    legend_label.pack(fill=tk.X, pady=(0, 6))

    overlay_var = BooleanVar(value=False)
    alpha_var = IntVar(value=35)
    outline_var = BooleanVar(value=False)

    label_search_var = tk.StringVar(value="")

    label_vars = {}
    labels_canvas = None
    labels_frame = None

    def refresh_legend():
        lc = state.get("overlay_label_colors") or {}
        names = state.get("overlay_label_names") or {}

        if state.get("mask_volume") is None:
            legend_label.config(text="")
            return

        if len(lc) == 0:
            legend_label.config(text="Overlay: binary")
            return

        items = []
        for lbl in sorted(lc.keys()):
            lbl_i = int(lbl)
            nm = names.get(lbl_i)
            items.append(f"{lbl_i}:{nm}" if nm else f"{lbl_i}")
            if len(items) >= 6:
                break
        more = f" (+{len(lc) - 6} more)" if len(lc) > 6 else ""
        legend_label.config(text="Overlay labels: " + ", ".join(items) + more)

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

    def _sync_labels_scrollregion(_event=None):
        if labels_canvas is None:
            return
        labels_canvas.configure(scrollregion=labels_canvas.bbox("all"))

    def on_label_visibility_change(lbl_i):
        vis = state.get("overlay_label_visible") or {}
        v = label_vars.get(int(lbl_i))
        if v is None:
            return
        vis[int(lbl_i)] = bool(v.get())
        state["overlay_label_visible"] = vis
        display_current_slice()

    def rebuild_label_checkboxes():
        if labels_frame is None:
            return

        for w in labels_frame.winfo_children():
            w.destroy()
        label_vars.clear()

        lc = state.get("overlay_label_colors") or {}
        vis = state.get("overlay_label_visible") or {}
        names = state.get("overlay_label_names") or {}
        if len(lc) == 0:
            _sync_labels_scrollregion()
            return

        q = (label_search_var.get() or "").strip().lower()

        tk.Label(labels_frame, text="Visible labels:", anchor="w", bg=theme["bg"], fg=theme["text"]).pack(anchor="w", pady=(0, 4))

        for lbl in sorted(lc.keys()):
            lbl_i = int(lbl)
            name = names.get(lbl_i, "")
            txt = f"Label {lbl_i}" + (f" ({name})" if name else "")

            if q:
                if q not in str(lbl_i) and q not in name.lower():
                    continue

            v = BooleanVar(value=bool(vis.get(lbl_i, True)))
            label_vars[lbl_i] = v

            cb = Checkbutton(
                labels_frame,
                text=txt,
                variable=v,
                command=(lambda lid=lbl_i: on_label_visibility_change(lid)),
                bg=theme["bg"],
                fg=theme["text"],
                activebackground=theme["bg"],
                selectcolor=theme["bg"],
            )
            cb.pack(anchor="w")

        _sync_labels_scrollregion()

    def _on_search_changed(*_args):
        rebuild_label_checkboxes()

    label_search_var.trace_add("write", _on_search_changed)

    def set_all_labels(val: bool):
        vis = state.get("overlay_label_visible") or {}
        for k in list(vis.keys()):
            vis[int(k)] = bool(val)
        state["overlay_label_visible"] = vis
        rebuild_label_checkboxes()
        display_current_slice()

    def invert_labels():
        vis = state.get("overlay_label_visible") or {}
        for k in list(vis.keys()):
            vis[int(k)] = not bool(vis[int(k)])
        state["overlay_label_visible"] = vis
        rebuild_label_checkboxes()
        display_current_slice()

    def load_mask_from_path(mask_path: str, quiet: bool = False) -> bool:
        if not mask_path or not os.path.exists(mask_path):
            return False

        try:
            m = overlay_utils.load_mask(mask_path)
        except Exception:
            return False

        state["mask_path"] = mask_path
        state["mask_volume"] = m
        state["overlay_enabled"] = True
        state["overlay_warned_mismatch"] = False

        state["overlay_label_colors"] = overlay_utils.default_label_colormap(m)
        lc = state["overlay_label_colors"] or {}
        state["overlay_label_visible"] = {int(lbl): True for lbl in lc.keys()}

        state["overlay_label_names"] = overlay_utils.load_label_names_for_mask(mask_path)

        overlay_var.set(True)
        alpha_var.set(state["overlay_alpha"])
        outline_var.set(state["overlay_outline"])

        refresh_legend()
        rebuild_label_checkboxes()

        if not quiet:
            messagebox.showinfo("Load Mask", f"Mask loaded:\n{os.path.basename(mask_path)}", parent=root)

        return True

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
        ok = load_mask_from_path(mask_path, quiet=True)
        if not ok:
            messagebox.showerror("Load Mask", "Failed to load mask.", parent=root)
            return
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

    def confirm_clear_mask():
        if _confirm("Clear Mask", "Clear the loaded mask and overlay settings?"):
            clear_mask()

    def load_labelmap_dialog():
        path = filedialog.askopenfilename(
            title="Select label-map JSON",
            initialdir=".",
            filetypes=[("JSON files", "*.json"), ("All files", "*")],
        )
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            if isinstance(data, dict) and "labels" in data and isinstance(data["labels"], dict):
                data = data["labels"]
            if not isinstance(data, dict):
                raise ValueError("Invalid label-map format.")

            out = {}
            for k, v in data.items():
                try:
                    kk = int(k)
                except Exception:
                    continue
                if isinstance(v, str) and v.strip():
                    out[kk] = v.strip()

            state["overlay_label_names"] = out
            refresh_legend()
            rebuild_label_checkboxes()
            display_current_slice()
        except Exception as e:
            messagebox.showerror("Label-map", f"Failed:\n{e}", parent=root)

    sec_mask = CollapsibleSection(overlay_frame, "Mask", theme=theme, open_by_default=True)
    sec_mask.pack(fill=tk.X, pady=(4, 6))

    sec_appearance = CollapsibleSection(overlay_frame, "Appearance", theme=theme, open_by_default=False)
    sec_appearance.pack(fill=tk.X, pady=(4, 6))

    sec_labels = CollapsibleSection(overlay_frame, "Labels", theme=theme, open_by_default=True)
    sec_labels.pack(fill=tk.BOTH, expand=True, pady=(4, 6))

    tk.Button(sec_mask.content, text="Load Mask", command=load_mask_dialog).pack(anchor="w")
    tk.Button(sec_mask.content, text="Clear Mask", command=clear_mask).pack(anchor="w", pady=(2, 6))
    tk.Button(sec_mask.content, text="Load Label-Map (JSON)", command=load_labelmap_dialog).pack(anchor="w")

    Checkbutton(
        sec_mask.content,
        text="Show Segmentation Overlay",
        variable=overlay_var,
        command=toggle_overlay,
        bg=theme["bg"],
        fg=theme["text"],
        activebackground=theme["bg"],
        selectcolor=theme["bg"],
    ).pack(anchor="w", pady=(8, 0))

    Checkbutton(
        sec_appearance.content,
        text="Overlay Outline Only",
        variable=outline_var,
        command=toggle_outline,
        bg=theme["bg"],
        fg=theme["text"],
        activebackground=theme["bg"],
        selectcolor=theme["bg"],
    ).pack(anchor="w")

    Scale(
        sec_appearance.content,
        from_=0,
        to=100,
        label="Overlay Alpha (%)",
        variable=alpha_var,
        orient=tk.HORIZONTAL,
        command=on_alpha_change,
    ).pack(fill=tk.X, pady=(4, 0))

    search_row = tk.Frame(sec_labels.content, bg=theme["bg"])
    search_row.pack(fill=tk.X, pady=(0, 6))
    tk.Label(search_row, text="Search:", bg=theme["bg"], fg=theme["text"]).pack(side=tk.LEFT)
    ttk.Entry(search_row, textvariable=label_search_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0))

    actions_row = tk.Frame(sec_labels.content, bg=theme["bg"])
    actions_row.pack(fill=tk.X, pady=(0, 6))
    tk.Button(actions_row, text="All", command=lambda: set_all_labels(True)).pack(side=tk.LEFT, padx=(0, 6))
    tk.Button(actions_row, text="None", command=lambda: set_all_labels(False)).pack(side=tk.LEFT, padx=(0, 6))
    tk.Button(actions_row, text="Invert", command=invert_labels).pack(side=tk.LEFT)

    labels_outer = tk.Frame(sec_labels.content, bg=theme["bg"])
    labels_outer.pack(fill=tk.BOTH, expand=True)

    labels_canvas = tk.Canvas(labels_outer, highlightthickness=0, bg=theme["bg"])
    labels_scroll = tk.Scrollbar(labels_outer, orient=tk.VERTICAL, command=labels_canvas.yview)
    labels_canvas.configure(yscrollcommand=labels_scroll.set)

    labels_scroll.pack(side=tk.RIGHT, fill=tk.Y)
    labels_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    labels_frame = tk.Frame(labels_canvas, bg=theme["bg"])
    labels_canvas.create_window((0, 0), window=labels_frame, anchor="nw")
    labels_frame.bind("<Configure>", _sync_labels_scrollregion)

    # Metadata window
    metadata_win = tk.Toplevel(root)
    metadata_win.title("File Metadata")
    metadata_label = tk.Label(metadata_win, font=("Arial", 12), justify="left", anchor="w")
    metadata_label.pack(padx=10, pady=10)

    # Presets (save/restore)
    def collect_current_preset() -> dict:
        return {
            "preprocessing": {
                "hist_eq": bool(settings["hist_eq"].get()),
                "colormap": bool(settings["colormap"].get()),
                "brightness_contrast": bool(settings["brightness_contrast"].get()),
                "brightness": int(settings["brightness"].get()),
                "contrast": float(settings["contrast"].get()),
                "wl_enabled": bool(settings["wl_enabled"].get()),
                "wl_center": int(settings["wl_center"].get()),
                "wl_width": int(settings["wl_width"].get()),
            },
            "overlay": {
                "overlay_enabled": bool(overlay_var.get()),
                "overlay_alpha": int(alpha_var.get()),
                "overlay_outline": bool(outline_var.get()),
                "mask_path": state.get("mask_path"),
                "label_visible": state.get("overlay_label_visible"),
                "label_names": state.get("overlay_label_names"),
            },
        }

    def apply_preset_dict(preset: dict, redraw: bool = True) -> bool:
        if not isinstance(preset, dict):
            return False

        pre = preset.get("preprocessing", {})
        if isinstance(pre, dict):
            settings["hist_eq"].set(bool(pre.get("hist_eq", False)))
            settings["colormap"].set(bool(pre.get("colormap", False)))
            settings["brightness_contrast"].set(bool(pre.get("brightness_contrast", False)))
            settings["brightness"].set(int(pre.get("brightness", 0)))
            try:
                settings["contrast"].set(float(pre.get("contrast", 1)))
            except Exception:
                settings["contrast"].set(1)
            settings["wl_enabled"].set(bool(pre.get("wl_enabled", False)))
            try:
                settings["wl_center"].set(int(pre.get("wl_center", 40)))
            except Exception:
                settings["wl_center"].set(40)
            try:
                settings["wl_width"].set(int(pre.get("wl_width", 400)))
            except Exception:
                settings["wl_width"].set(400)
        _update_wl_ui_enabled()

        ov = preset.get("overlay", {})
        if isinstance(ov, dict):
            try:
                alpha_var.set(int(ov.get("overlay_alpha", 35)))
            except Exception:
                alpha_var.set(35)

            outline_var.set(bool(ov.get("overlay_outline", False)))
            state["overlay_outline"] = bool(outline_var.get())

            mask_path = ov.get("mask_path")
            if isinstance(mask_path, str) and mask_path.strip() and os.path.exists(mask_path):
                # Load mask silently
                load_mask_from_path(mask_path, quiet=True)

            # label visibility
            lv = ov.get("label_visible")
            if isinstance(lv, dict):
                out_lv = {}
                for k, v in lv.items():
                    try:
                        kk = int(k)
                    except Exception:
                        continue
                    out_lv[kk] = bool(v)
                state["overlay_label_visible"] = out_lv
                rebuild_label_checkboxes()

            # label names
            ln = ov.get("label_names")
            if isinstance(ln, dict):
                out_ln = {}
                for k, v in ln.items():
                    try:
                        kk = int(k)
                    except Exception:
                        continue
                    if isinstance(v, str) and v.strip():
                        out_ln[kk] = v.strip()
                state["overlay_label_names"] = out_ln
                refresh_legend()
                rebuild_label_checkboxes()

            overlay_var.set(bool(ov.get("overlay_enabled", overlay_var.get())))
            toggle_overlay()

        if redraw:
            display_current_slice()
        return True

    _update_wl_ui_enabled()

    def save_session_preset():
        path = file_paths[state["current_file_index"]]
        key = _preset_key(path)
        presets = _load_presets()
        presets[key] = collect_current_preset()
        _save_presets(presets)
        messagebox.showinfo("Session Preset", "Preset saved for this file.", parent=root)

    def apply_session_preset(show_message: bool = True):
        path = file_paths[state["current_file_index"]]
        key = _preset_key(path)
        presets = _load_presets()
        preset = presets.get(key)
        if not preset:
            if show_message:
                messagebox.showinfo("Session Preset", "No preset found for this file.", parent=root)
            return False
        ok = apply_preset_dict(preset, redraw=True)
        if ok and show_message:
            messagebox.showinfo("Session Preset", "Preset applied.", parent=root)
        return ok

    # Status update
    def update_status():
        parts = []
        parts.append(f"File {state['current_file_index'] + 1}/{len(file_paths)}")
        ft = state.get("current_file_type") or "Unknown"
        parts.append(ft)

        if state["volume"] is not None and ft not in ["JPEG/PNG", "TIFF"]:
            parts.append(f"Z {state['z_index'] + 1}/{max(1, state['z_max'])}")
            parts.append(f"T {state['t_index'] + 1}/{max(1, state['t_max'])}")

        if state.get("zoom_enabled"):
            parts.append(f"Zoom {state.get('zoom_factor', 1.0):.2f}")

        if state.get("overlay_enabled") and state.get("mask_volume") is not None:
            parts.append(f"Overlay {state.get('overlay_alpha', 35)}%")

        insp = state.get("inspector_text", "")
        if insp:
            parts.append(insp)

        status_label.config(text=" | ".join(parts))

        if state.get("is_ct", False) and bool(settings["wl_enabled"].get()):
            parts.append(f"WL {settings['wl_center'].get()}/{settings['wl_width'].get()}")

    # Zoom/Pan events
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

    # Pixel inspector helpers
    def _image_top_left_in_label():
        scaled = state.get("last_disp_scaled_wh")
        if not scaled:
            return None
        img_w, img_h = scaled
        lw = max(1, image_label.winfo_width())
        lh = max(1, image_label.winfo_height())
        ox = (lw - img_w) // 2
        oy = (lh - img_h) // 2
        return ox, oy, img_w, img_h

    def on_mouse_move(event):
        out = state.get("last_disp_out")
        base_wh = state.get("last_disp_base_wh")
        scaled_wh = state.get("last_disp_scaled_wh")
        if out is None or base_wh is None or scaled_wh is None:
            state["inspector_text"] = ""
            update_status()
            return

        tl = _image_top_left_in_label()
        if tl is None:
            state["inspector_text"] = ""
            update_status()
            return

        ox, oy, img_w, img_h = tl
        if not (ox <= event.x < ox + img_w and oy <= event.y < oy + img_h):
            state["inspector_text"] = ""
            update_status()
            return

        w, h = base_wh
        xs = int(np.clip(event.x - ox, 0, img_w - 1))
        ys = int(np.clip(event.y - oy, 0, img_h - 1))

        x = int(np.clip(xs * (w / max(1, img_w)), 0, w - 1))
        y = int(np.clip(ys * (h / max(1, img_h)), 0, h - 1))

        px = out[y, x]
        if out.ndim == 2:
            val_txt = f"I={int(px)}"
        else:
            r, g, b = int(px[0]), int(px[1]), int(px[2])
            val_txt = f"RGB=({r},{g},{b})"

        lbl_txt = ""
        m = state.get("last_mask_scaled")
        if m is not None:
            my = int(np.clip(ys, 0, m.shape[0] - 1))
            mx = int(np.clip(xs, 0, m.shape[1] - 1))
            lbl = int(m[my, mx])
            if lbl != 0:
                nm = (state.get("overlay_label_names") or {}).get(lbl)
                lbl_txt = f"  |  Label={lbl}" + (f" ({nm})" if nm else "")

        state["inspector_text"] = f"x={x}, y={y}  |  {val_txt}{lbl_txt}"
        update_status()

    def on_mouse_leave(_event):
        state["inspector_text"] = ""
        update_status()

    def _apply_window_level_to_8bit(img_hu: np.ndarray, center: float, width: float) -> np.ndarray:
        """
        Map HU image -> uint8 using Window/Level.
        Output range is 0..255 float32 (still ok for your downstream pipeline).
        """
        w = float(max(1.0, width))
        c = float(center)

        lo = c - (w / 2.0)
        hi = c + (w / 2.0)

        out = (img_hu - lo) / (hi - lo)
        out = np.clip(out, 0.0, 1.0) * 255.0
        return out.astype(np.float32)

    # Display pipeline
    def build_display_image():
        vol = state["volume"]
        if vol is None:
            state["last_disp_out"] = None
            state["last_disp_base_wh"] = None
            state["last_disp_scaled_wh"] = None
            state["last_mask_scaled"] = None
            return None

        ft = state["current_file_type"]
        is_rgb = (ft in ["JPEG/PNG", "TIFF"] and vol.ndim == 3 and vol.shape[2] == 3)

        if is_rgb:
            slice_2d = vol.astype(np.float32)
        else:
            slice_src = vol[..., state["z_index"], state["t_index"]].astype(np.float32)

            # Apply WL for any grayscale volume when enabled
            if bool(settings["wl_enabled"].get()):
                c = float(settings["wl_center"].get())
                wwl = float(settings["wl_width"].get())
                slice_2d = _apply_window_level_to_8bit(slice_src, c, wwl)
            else:
                # Generic normalization for non-CT (or CT when WL is disabled)
                mn, mx = float(np.min(slice_src)), float(np.max(slice_src))
                if mx > mn:
                    slice_2d = (slice_src - mn) / (mx - mn) * 255.0
                else:
                    slice_2d = np.zeros_like(slice_src, dtype=np.float32)

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

        h, w = out.shape[:2]
        state["last_disp_out"] = out
        state["last_disp_base_wh"] = (w, h)

        fw = max(1, image_frame.winfo_width() - 10)
        fh = max(1, image_frame.winfo_height() - 10)
        scale = min(fw / w, fh / h) if fw > 1 and fh > 1 else 1.0
        new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))
        state["last_disp_scaled_wh"] = (new_w, new_h)

        if out.ndim == 2:
            pil = Image.fromarray(out, "L")
        else:
            pil = Image.fromarray(out, "RGB")

        if (new_w, new_h) != (w, h):
            pil = pil.resize((new_w, new_h), Image.BILINEAR)

        state["last_mask_scaled"] = None

        if state["overlay_enabled"] and state["mask_volume"] is not None:
            m = overlay_utils.get_mask_slice(state["mask_volume"], state["z_index"], state["t_index"])
            m = np.nan_to_num(m)
            m = np.rint(m).astype(np.int32)

            mh, mw = m.shape[:2]
            if (mw != w or mh != h) and not state.get("overlay_warned_mismatch", False):
                state["overlay_warned_mismatch"] = True
                print(f"[WARN] Mask shape {mw}x{mh} != image slice {w}x{h}. Resizing mask to match.")

            m = overlay_utils.resize_mask_nearest(m, w, h)
            m = image_processing.apply_zoom_and_pan_mask(m, state["zoom_factor"], state["pan_x"], state["pan_y"])
            m = overlay_utils.resize_mask_nearest(m, new_w, new_h).astype(np.int32)

            state["last_mask_scaled"] = m

            alpha = float(state.get("overlay_alpha", 35)) / 100.0

            if state["overlay_label_colors"] is None:
                m_bin = overlay_utils.to_binary_mask(m)
                pil = overlay_utils.apply_overlay_to_pil(pil, m_bin, alpha)
            else:
                try:
                    pil = overlay_utils.apply_multiclass_overlay_to_pil(
                        pil,
                        m,
                        label_colors=state["overlay_label_colors"],
                        alpha=alpha,
                        outline=state["overlay_outline"],
                        label_visible=state.get("overlay_label_visible"),
                    )
                except TypeError:
                    pil = overlay_utils.apply_multiclass_overlay_to_pil(
                        pil,
                        m,
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

    # Loading
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
            arr = None

            # Prefer series stacking, but always fallback to single-file load.
            try:
                vol3d, meta_series, meta_dict = image_loader.load_dicom_series_from_file(path)
                arr = vol3d  # (H,W,Z) float32
                state["dicom_meta"] = meta_dict
                state["is_ct"] = (str(meta_dict.get("Modality", "")).upper() == "CT")

                # If CT and tags exist, initialize WL and enable it by default
                if state["is_ct"]:
                    wc = meta_dict.get("WindowCenter", None)
                    ww = meta_dict.get("WindowWidth", None)
                    if wc is not None and ww is not None:
                        try:
                            settings["wl_center"].set(int(round(float(wc))))
                            settings["wl_width"].set(int(round(float(ww))))
                            settings["wl_enabled"].set(True)
                        except Exception:
                            pass
                else:
                    settings["wl_enabled"].set(False)

                # Override metadata label with series-aware metadata
                metadata_label.config(text=meta_series)
            except Exception as e:
                print(f"[WARN] load_dicom_series_from_file failed: {e}. Falling back to single-file DICOM.")
                state["dicom_meta"] = None
                state["is_ct"] = False
                settings["wl_enabled"].set(False)

                try:
                    arr = image_loader.load_dicom(path)  # your old single-file loader
                except Exception as e2:
                    print(f"[ERROR] Single-file DICOM load failed: {e2}")
                    arr = None

        elif file_type == "NIfTI":
            arr = nib.load(path).get_fdata()
        elif file_type == "JPEG/PNG":
            arr = image_loader.load_jpeg_png(path)
        elif file_type == "TIFF":
            arr = image_loader.load_tiff(path)
        elif file_type == "WHOLESLIDE":
            arr = image_loader.load_whole_slide_downsampled(path)

        if file_type != "DICOM":
            state["dicom_meta"] = None
            state["is_ct"] = False

        if arr is None:
            state["volume"] = None
        else:
            is_rgb_2d = (file_type in ["JPEG/PNG", "TIFF"] and arr.ndim == 3 and arr.shape[2] == 3)
            if is_rgb_2d:
                state["volume"] = arr
            else:
                if arr.ndim == 2:
                    arr = arr[..., np.newaxis, np.newaxis]
                elif arr.ndim == 3:
                    arr = arr[..., np.newaxis]
                state["volume"] = arr

        if state["volume"] is None:
            state["z_max"] = 1
            state["t_max"] = 1
            state["z_index"] = 0
            state["t_index"] = 0
            z_slider.pack_forget()
            t_slider.pack_forget()
        else:
            vol_shape = state["volume"].shape
            is_rgb_2d = (file_type in ["JPEG/PNG", "TIFF"] and len(vol_shape) == 3 and vol_shape[2] == 3)

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

        state["zoom_factor"] = 1.0
        state["pan_x"] = 0.0
        state["pan_y"] = 0.0
        _update_wl_ui_enabled()

        # Auto-apply preset if exists (silent)
        apply_session_preset(show_message=False)

        display_current_slice()

    # Resize throttle
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
                print("[ERROR] display_current_slice on resize:", e)

        root.after(60, do_redraw)

    root.bind("<Configure>", on_root_resize)

    root.bind("<MouseWheel>", on_mouse_wheel)
    root.bind("<Button-4>", lambda e: scroll_zoom(+1))
    root.bind("<Button-5>", lambda e: scroll_zoom(-1))

    def _safe_change_file(delta):
        if len(file_paths) <= 1:
            return
        change_file(delta)

    def _safe_change_z(delta):
        if state.get("z_max", 1) <= 1:
            return
        state["z_index"] = int(np.clip(state["z_index"] + delta, 0, state["z_max"] - 1))
        z_slider.set(state["z_index"])
        display_current_slice()

    def _safe_change_t(delta):
        if state.get("t_max", 1) <= 1:
            return
        state["t_index"] = int(np.clip(state["t_index"] + delta, 0, state["t_max"] - 1))
        t_slider.set(state["t_index"])
        display_current_slice()

    root.bind("<Left>", lambda e: _safe_change_file(-1))
    root.bind("<Right>", lambda e: _safe_change_file(+1))
    root.bind("<Up>", lambda e: _safe_change_z(+1))
    root.bind("<Down>", lambda e: _safe_change_z(-1))
    root.bind("<Prior>", lambda e: _safe_change_t(+1))
    root.bind("<Next>", lambda e: _safe_change_t(-1))

    root.bind("o", lambda e: (overlay_var.set(not overlay_var.get()), toggle_overlay()))
    root.bind("r", lambda e: reset_view())
    root.bind("p", lambda e: reset_preprocessing())
    root.bind("e", lambda e: export_current_view())

    image_label.bind("<Button-1>", on_left_down)
    image_label.bind("<B1-Motion>", on_left_drag)
    image_label.bind("<ButtonRelease-1>", on_left_up)

    image_label.bind("<Motion>", on_mouse_move)
    image_label.bind("<Leave>", on_mouse_leave)

    # Bottom-right Quick Actions (5 buttons)
    tk.Button(quick_actions, text="Reset View", command=confirm_reset_view).pack(side=tk.LEFT, padx=(0, 6))
    tk.Button(quick_actions, text="Reset Preproc", command=confirm_reset_preproc).pack(side=tk.LEFT, padx=(0, 6))
    tk.Button(quick_actions, text="Clear Mask", command=confirm_clear_mask).pack(side=tk.LEFT, padx=(0, 6))
    tk.Button(quick_actions, text="Save Preset", command=save_session_preset).pack(side=tk.LEFT, padx=(0, 6))
    tk.Button(quick_actions, text="Apply Preset", command=lambda: apply_session_preset(show_message=True)).pack(side=tk.LEFT)

    # Theme
    try:
        ui_theme.apply_viewer_theme(root, exclude_widgets=[image_frame, image_label])
        ui_theme.apply_viewer_theme(metadata_win)
    except Exception:
        _safe_apply_viewer_theme(root, theme, exclude_widgets=[image_frame, image_label])
        _safe_apply_viewer_theme(metadata_win, theme)

    refresh_legend()
    rebuild_label_checkboxes()

    file_slider.set(0)
    load_current_file()

    root.after(200, lambda: main_pane.sashpos(0, int(root.winfo_width() * 0.72)))
    root.mainloop()
