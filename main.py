# main.py

import os
from pathlib import Path
import json
import tkinter as tk
from tkinter import filedialog, messagebox

import image_loader
import ui_theme
import viewer_multi_slicetime


APP_NAME = "SMIV"
MAX_RECENT = 10


def _config_dir() -> Path:
    d = Path.home() / ".smiv"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _recent_file_path() -> Path:
    return _config_dir() / "recent_files.json"


def load_recent_files() -> list:
    p = _recent_file_path()
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, list):
            out = []
            for x in data:
                if isinstance(x, str) and x.strip():
                    out.append(x)
            return out[:MAX_RECENT]
    except Exception:
        pass
    return []


def save_recent_files(paths: list) -> None:
    p = _recent_file_path()
    paths = [x for x in paths if isinstance(x, str) and x.strip()]
    p.write_text(json.dumps(paths[:MAX_RECENT], indent=2), encoding="utf-8")


def add_recent_file(path: str) -> None:
    path = os.path.abspath(path)
    rec = load_recent_files()
    rec = [p for p in rec if os.path.abspath(p) != path]
    rec.insert(0, path)
    # Keep only existing paths
    rec = [p for p in rec if os.path.exists(p)]
    save_recent_files(rec)


def clear_recent_files() -> None:
    save_recent_files([])


def scan_directory_for_images(dir_path: str) -> list:
    """
    Scans a directory and returns recognized image paths.

    IMPORTANT:
      - DICOM is grouped as ONE entry per SeriesInstanceUID (so folders with 300 slices won't flood the slider).
      - Non-DICOM files are added normally.
    """
    if not dir_path or not os.path.isdir(dir_path):
        return []

    all_files = sorted(os.listdir(dir_path))
    recognized = []

    seen_dicom_series = set()

    for f in all_files:
        full_p = os.path.join(dir_path, f)
        if not os.path.isfile(full_p):
            continue

        try:
            file_type, _ = image_loader.detect_file_type_and_metadata(full_p)
        except Exception:
            file_type = None

        if file_type == "DICOM":
            # Group by SeriesInstanceUID
            try:
                uid = image_loader.get_dicom_series_uid(full_p)
            except Exception:
                uid = None

            if uid:
                if uid in seen_dicom_series:
                    continue
                seen_dicom_series.add(uid)
                recognized.append(full_p)
            else:
                # If UID missing, keep it as a single item
                recognized.append(full_p)

        elif file_type in ["NIfTI", "JPEG/PNG", "TIFF", "WHOLESLIDE"]:
            recognized.append(full_p)

    return recognized


def _move_selected_to_front(recognized_paths: list, selected_path: str) -> list:
    """
    Ensures the selected item becomes the first item shown in the viewer.
    Special handling for DICOM: move the representative path of the selected series.
    """
    if not recognized_paths:
        return recognized_paths

    selected_path = os.path.abspath(selected_path)

    try:
        selected_type, _ = image_loader.detect_file_type_and_metadata(selected_path)
    except Exception:
        selected_type = None

    # DICOM: selected file may be a slice; recognized_paths likely has only 1 representative per series
    if selected_type == "DICOM":
        try:
            selected_uid = image_loader.get_dicom_series_uid(selected_path)
        except Exception:
            selected_uid = None

        if selected_uid:
            rep_idx = None
            for i, p in enumerate(recognized_paths):
                try:
                    uid_i = image_loader.get_dicom_series_uid(p)
                except Exception:
                    uid_i = None
                if uid_i == selected_uid:
                    rep_idx = i
                    break

            if rep_idx is not None:
                rep = recognized_paths.pop(rep_idx)
                recognized_paths.insert(0, rep)
                return recognized_paths

        # Fallback: if no UID match found, just force selected_path to front
        # (may duplicate, but better than opening a different series)
        recognized_paths = [p for p in recognized_paths if os.path.abspath(p) != selected_path]
        recognized_paths.insert(0, selected_path)
        return recognized_paths

    # Non-DICOM: move the exact file to front if present
    recognized_paths = [p for p in recognized_paths if os.path.abspath(p) != selected_path]
    recognized_paths.insert(0, selected_path)
    return recognized_paths


def open_viewer_with_selected_file(file_path: str, modality: str = "AUTO"):
    if not file_path or not os.path.isfile(file_path):
        return

    add_recent_file(file_path)

    dir_path = os.path.dirname(file_path)
    recognized_paths = scan_directory_for_images(dir_path)
    if not recognized_paths:
        messagebox.showwarning(APP_NAME, "No supported image files were found in the selected file's folder.")
        return

    recognized_paths = _move_selected_to_front(recognized_paths, file_path)

    viewer_multi_slicetime.create_viewer(recognized_paths, modality)


def open_viewer_with_folder(dir_path: str, modality: str = "AUTO"):
    if not dir_path or not os.path.isdir(dir_path):
        return

    recognized_paths = scan_directory_for_images(dir_path)
    if not recognized_paths:
        messagebox.showwarning(APP_NAME, "No supported image files were found in the selected folder.")
        return

    # Store something meaningful in recents: the first recognized entry (series rep / file)
    add_recent_file(recognized_paths[0])
    viewer_multi_slicetime.create_viewer(recognized_paths, modality)


def parse_dnd_files(data: str) -> list:
    """
    Parse TkDND file list. On Windows/macOS it may wrap paths with braces.
    """
    if not data:
        return []

    data = data.strip()
    out = []
    buf = ""
    in_brace = False

    for ch in data:
        if ch == "{":
            in_brace = True
            buf = ""
        elif ch == "}":
            in_brace = False
            if buf.strip():
                out.append(buf.strip())
            buf = ""
        elif ch.isspace() and not in_brace:
            if buf.strip():
                out.append(buf.strip())
            buf = ""
        else:
            buf += ch

    if buf.strip():
        out.append(buf.strip())

    # Normalize
    out2 = []
    for p in out:
        p = p.strip().strip('"')
        if p:
            out2.append(p)
    return out2


def main():
    # Optional Drag-and-Drop (cross-platform) via tkinterdnd2
    DND_AVAILABLE = False
    TkRoot = tk.Tk
    DND_FILES = None

    try:
        from tkinterdnd2 import TkinterDnD, DND_FILES as _DND_FILES  # type: ignore
        TkRoot = TkinterDnD.Tk
        DND_FILES = _DND_FILES
        DND_AVAILABLE = True
    except Exception:
        DND_AVAILABLE = False

    root = TkRoot()

    widgets = {}

    def refresh_recent_list():
        rec = load_recent_files()
        lb = widgets.get("recent_listbox")
        if lb is None:
            return
        lb.delete(0, tk.END)
        for p in rec:
            lb.insert(tk.END, p)

        hint = widgets.get("recent_hint_label")
        if hint is not None:
            if rec:
                hint.config(text="Double-click a recent item to open it.")
            else:
                hint.config(text="No recent files yet.")

    def on_load_scan():
        file_path = filedialog.askopenfilename(
            title="Select a file",
            initialdir=".",
            filetypes=[
                ("All files (including no extension)", "*"),
                ("DICOM Files", "*.dcm"),
                ("NIfTI Files (.nii/.nii.gz)", "*.nii *.nii.gz"),
                ("PNG/JPG Images", "*.png *.jpg *.jpeg"),
                ("TIFF/WSI Images", "*.tif *.tiff *.svs *.ndpi *.scn *.mrxs"),
            ],
        )
        if not file_path:
            return
        open_viewer_with_selected_file(file_path, modality="AUTO")
        refresh_recent_list()

    def on_open_folder():
        dir_path = filedialog.askdirectory(title="Select a folder", initialdir=".")
        if not dir_path:
            return
        open_viewer_with_folder(dir_path, modality="AUTO")
        refresh_recent_list()

    def on_open_recent(path: str):
        if not path:
            return
        path = os.path.abspath(path)

        if os.path.isdir(path):
            open_viewer_with_folder(path, modality="AUTO")
        else:
            open_viewer_with_selected_file(path, modality="AUTO")

        refresh_recent_list()

    def on_clear_recent():
        if messagebox.askyesno(APP_NAME, "Clear the recent files list?", parent=root):
            clear_recent_files()
            refresh_recent_list()

    widgets = ui_theme.setup_ui(
        root,
        on_load_scan=on_load_scan,
        on_open_folder=on_open_folder,
        on_open_recent=on_open_recent,
        on_clear_recent=on_clear_recent,
        dnd_available=DND_AVAILABLE,
    )

    refresh_recent_list()

    # Enable drag-and-drop if available
    if DND_AVAILABLE and DND_FILES is not None:
        def _on_drop(event):
            paths = parse_dnd_files(getattr(event, "data", ""))
            if not paths:
                return

            first = os.path.abspath(paths[0])

            if os.path.isdir(first):
                open_viewer_with_folder(first, modality="AUTO")
            else:
                open_viewer_with_selected_file(first, modality="AUTO")

            refresh_recent_list()

        try:
            root.drop_target_register(DND_FILES)
            root.dnd_bind("<<Drop>>", _on_drop)
        except Exception:
            pass

    root.mainloop()


if __name__ == "__main__":
    main()
