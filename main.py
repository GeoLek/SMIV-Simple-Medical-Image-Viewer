#main.py
# main.py

import os
import tkinter as tk
from tkinter import filedialog
import nibabel as nib
import image_loader
import viewer_multi_slicetime  # The new multi-file, multi-slice/time viewer
import ui_theme

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
        ]
    )
    if not file_path:
        return  # User canceled

    dir_path = os.path.dirname(file_path)
    all_files = sorted(os.listdir(dir_path))

    recognized_paths = []
    for f in all_files:
        full_p = os.path.join(dir_path, f)
        if os.path.isfile(full_p):
            file_type, _ = image_loader.detect_file_type_and_metadata(full_p)
            if file_type in ["DICOM", "NIfTI", "JPEG/PNG"]:
                recognized_paths.append(full_p)

    if not recognized_paths:
        print("No recognized files in directory.")
        return

    # Launch multi-file, multi-slice/time viewer
    viewer_multi_slicetime.create_viewer(recognized_paths, modality)

def main():
    root = tk.Tk()
    ui_theme.setup_ui(root, select_modality)
    root.mainloop()

if __name__ == "__main__":
    main()
