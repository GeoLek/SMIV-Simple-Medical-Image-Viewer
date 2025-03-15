import pydicom
import nibabel as nib
import numpy as np
from PIL import Image

def detect_file_type(file_path):
    """
    Detect whether a file is DICOM, NIfTI, or JPEG/PNG
    based on its content (not relying on extension).
    Prints dimension/header info if available.
    """
    # 1) Try DICOM
    try:
        dcm_data = pydicom.dcmread(file_path, stop_before_pixels=False)
        if dcm_data:
            print("========== DICOM Info ==========")
            print(dcm_data)  # Summarized DICOM header
            shape = dcm_data.pixel_array.shape
            print(f"Detected shape: {shape}")
            if len(shape) == 2:
                print("=> This is a 2D DICOM.")
            elif len(shape) == 3:
                print("=> Possibly multi-frame or 3D DICOM.")
            print("================================\n")
            return "DICOM"
    except Exception:
        pass

    # 2) Try NIfTI
    try:
        nii_data = nib.load(file_path)
        if nii_data:
            hdr = nii_data.header
            shape = nii_data.shape
            print("========== NIfTI Info ==========")
            print(hdr)  # Full NIfTI header
            print(f"Detected shape: {shape}")
            print(f"=> This is a {len(shape)}D NIfTI.")
            print("================================\n")
            return "NIfTI"
    except Exception:
        pass

    # 3) Try JPEG/PNG via Pillow
    try:
        with Image.open(file_path) as img:
            img.verify()  # If no error => valid image
        print("=> Detected a JPEG/PNG image (2D).")
        return "JPEG/PNG"
    except Exception:
        pass

    print("Error: Unknown or unsupported file format.")
    return None

def load_dicom(file_path):
    """ Load DICOM image and return normalized NumPy array [0..255] in float32. """
    dicom_data = pydicom.dcmread(file_path)
    img_array = dicom_data.pixel_array.astype(np.float32)
    # Normalize
    min_val, max_val = img_array.min(), img_array.max()
    if max_val != min_val:
        img_array = (img_array - min_val) / (max_val - min_val) * 255
    return img_array

def load_nifti(file_path):
    """ Load NIfTI image (2D, 3D, or 4D) and return as float64 array. """
    nii_data = nib.load(file_path)
    img_array = nii_data.get_fdata()  # shape could be (X, Y), (X, Y, Z), or (X, Y, Z, T)
    return img_array

def load_jpeg_png(file_path):
    """ Load JPEG/PNG (any Pillow-supported format) and return float32 [0..255] in grayscale. """
    with Image.open(file_path).convert("L") as img:
        return np.array(img, dtype=np.float32)
