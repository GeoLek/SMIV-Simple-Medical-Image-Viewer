# main.py

import os
import tkinter as tk
from tkinter import filedialog
import nibabel as nib
import image_loader
import ui_theme
import viewer_multi_slicetime

def select_modality(modality):
    open_file_viewer(modality)

def open_file_viewer(modality):
    file_path = filedialog.askopenfilename(
        title="Select a file",
        initialdir=".",
        filetypes=[
            ("All files (including no extension)", "*"),
            ("DICOM Files", "*.dcm"),
            ("NIfTI Files (.nii/.nii.gz)", "*.nii *.nii.gz"),
            ("PNG/JPG Images", "*.png *.jpg *.jpeg"),
            ("TIFF/WSI Images", "*.tif *.tiff *.svs *.ndpi *.scn *.mrxs"),
        ]
    )
    if not file_path:
        return  # User canceled

    dir_path = os.path.dirname(file_path)
    all_files = sorted(os.listdir(dir_path))

    recognized_paths = []
    for f in all_files:
        full_p = os.path.join(dir_path, f)
        print(f"[DEBUG] Checking: {full_p}")
        if os.path.isfile(full_p):
            file_type, _ = image_loader.detect_file_type_and_metadata(full_p)
            print(f"[DEBUG] Result => file_type={file_type}")
            if file_type in ["DICOM", "NIfTI", "JPEG/PNG", "TIFF", "WHOLESLIDE"]:
                print("[DEBUG] => recognized. Appending to recognized_paths.")
                recognized_paths.append(full_p)
            else:
                print("[DEBUG] => Not recognized.")
        else:
            print("[DEBUG] => Not a file (maybe a subdir). Skipping.")

    print(f"[DEBUG] recognized_paths => {recognized_paths}")
    if not recognized_paths:
        print("[DEBUG] => recognized_paths is empty. No recognized image files in directory.")
        return

    # --- The key fix: move the chosen file_path to front of recognized_paths
    if file_path in recognized_paths:
        recognized_paths.remove(file_path)
        recognized_paths.insert(0, file_path)

    # Now the first file in recognized_paths is the one user selected
    viewer_multi_slicetime.create_viewer(recognized_paths, modality)

def main():
    root = tk.Tk()
    ui_theme.setup_ui(root, select_modality)
    root.mainloop()

if __name__ == "__main__":
    main()
