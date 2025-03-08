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
    and determines if it's 2D or 3D by checking the data shape.
    """
    file_path = filedialog.askopenfilename(
        title="Select a file",
        initialdir=".",
        filetypes=[("All Files", "*.*")]  # Show absolutely everything
    )
    if not file_path:
        return  # User canceled selection

    file_type = image_loader.detect_file_type(file_path)

    # If JPEG/PNG => definitely 2D
    if file_type == "JPEG/PNG":
        viewer_2d.create_2d_viewer(file_path, modality)
        return

    if file_type == "DICOM":
        # DICOM: We only detect single-slice DICOM with this code.
        # If you have multi-slice (3D) DICOM, you'd need a series loader in viewer_3d.
        viewer_2d.create_2d_viewer(file_path, modality)

    elif file_type == "NIfTI":
        # Check if it's truly 3D or 2D
        try:
            nii_data = nib.load(file_path)
            shape = nii_data.shape
            # If there's a third dimension >1 => it's 3D
            if len(shape) == 3 and shape[2] > 1:
                # 3D volume
                viewer_3d.render_3d_image(file_path, modality)
            else:
                # 2D slice
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
