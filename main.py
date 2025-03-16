# main.py
import tkinter as tk
from tkinter import filedialog
import image_loader
import viewer_2d
import viewer_3d
import nibabel as nib

def select_modality(modality):
    """ Opens the appropriate viewer based on the selected modality. """
    if modality in ["MRI", "CT", "PET/CT", "EUS"]:
        open_file_viewer(modality)

def open_file_viewer(modality):
    """
    Opens a file dialog for the selected modality
    and determines if it's 2D, 3D, or 4D by checking the data shape.
    """
    file_path = filedialog.askopenfilename(
        title="Select a file",
        initialdir=".",
        filetypes=[("All Files", "*.*")]
    )
    if not file_path:
        return  # User canceled selection

    # Detect the file type and metadata
    file_type, _ = image_loader.detect_file_type_and_metadata(file_path)

    if file_type == "JPEG/PNG":
        # Definitely 2D
        viewer_2d.create_2d_viewer(file_path, modality)
        return

    elif file_type == "DICOM":
        # Check if it's a **3D multi-frame** DICOM (e.g., CT/MRI volume)
        img_array = image_loader.load_dicom(file_path)
        if img_array.ndim == 3 and img_array.shape[-1] > 1:
            viewer_3d.create_3d_viewer(file_path)
        else:
            viewer_2d.create_2d_viewer(file_path, modality)

    elif file_type == "NIfTI":
        # Check if it's truly 3D or 4D
        try:
            nii_data = nib.load(file_path)
            shape = nii_data.shape
            if len(shape) >= 3 and shape[2] > 1:
                viewer_3d.create_3d_viewer(file_path)  # Open in new viewer_3d.py
            else:
                viewer_2d.create_2d_viewer(file_path, modality)
        except Exception as e:
            print(f"Error reading NIfTI: {e}")
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
