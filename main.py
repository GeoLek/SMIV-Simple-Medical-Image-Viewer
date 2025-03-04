# main.py
import tkinter as tk
from tkinter import filedialog
import image_loader
import viewer_2d
import viewer_3d

def select_modality(modality):
    """ Opens the appropriate viewer based on the selected modality. """
    if modality in ["MRI", "CT", "PET/CT", "EUS"]:
        open_file_viewer(modality)

def open_file_viewer(modality):
    """
    Opens a file dialog for the selected modality and determines if it's 2D or 3D.
    For simplicity, we’ll assume 2D unless you specifically want 3D for some modalities.
    """
    file_path = filedialog.askopenfilename(
        title="Select a file",
        initialdir=".",
        filetypes=[("All Files", "*.*")]  # <-- Show absolutely everything
    )
    if not file_path:
        return  # User canceled selection

    # Detect format
    file_type = image_loader.detect_file_type(file_path)

    # Decide 2D or 3D. For example, let's say:
    # - DICOM or NIfTI is potentially 2D or 3D, but let's default to 2D.
    # - If you want to open 3D for certain modalities, you can do so here:
    if file_type in ["DICOM", "NIfTI", "JPEG/PNG"]:
        # For 2D
        viewer_2d.create_2d_viewer(file_path, modality)
    else:
        print("Error: Unsupported or unknown file format.")

def main():
    """ Launches the main selection window """
    root = tk.Tk()
    root.title("Select Imaging Modality")

    tk.Label(root, text="Select an Imaging Modality:", font=("Arial", 14)).pack(pady=10)

    btn_mri = tk.Button(root, text="MRI", command=lambda: select_modality("MRI"), width=20)
    btn_mri.pack(pady=5)

    btn_ct = tk.Button(root, text="CT", command=lambda: select_modality("CT"), width=20)
    btn_ct.pack(pady=5)

    btn_petct = tk.Button(root, text="PET/CT", command=lambda: select_modality("PET/CT"), width=20)
    btn_petct.pack(pady=5)

    btn_eus = tk.Button(root, text="EUS", command=lambda: select_modality("EUS"), width=20)
    btn_eus.pack(pady=5)

    root.mainloop()

if __name__ == "__main__":
    main()
