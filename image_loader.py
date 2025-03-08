# image_loader.py
import os
import pydicom
import nibabel as nib
import numpy as np
from PIL import Image

def detect_file_type(file_path):
    """
    Detect whether a file is DICOM, NIfTI, or JPEG/PNG
    based on its content (not relying on extension).
    """
    # 1) Try loading as DICOM
    try:
        dcm_data = pydicom.dcmread(file_path, stop_before_pixels=True)
        if dcm_data:  # If successful, it's DICOM
            return "DICOM"
    except Exception:
        pass

    # 2) Try loading as NIfTI
    try:
        nii_data = nib.load(file_path)
        if nii_data:
            return "NIfTI"
    except Exception:
        pass

    # 3) Try opening with Pillow => JPEG/PNG
    try:
        with Image.open(file_path) as img:
            img.verify()  # If no error -> It's a valid image
        return "JPEG/PNG"
    except Exception:
        pass

    return None  # Unknown or unsupported

def load_dicom(file_path):
    """ Load DICOM image and return normalized NumPy array """
    dicom_data = pydicom.dcmread(file_path)
    img_array = dicom_data.pixel_array.astype(np.float32)
    # Normalize
    min_val, max_val = img_array.min(), img_array.max()
    if max_val != min_val:
        img_array = (img_array - min_val) / (max_val - min_val) * 255
    return img_array

def load_nifti(file_path):
    """ Load NIfTI image and return NumPy array (could be 2D or 3D) """
    nii_data = nib.load(file_path)
    img_array = nii_data.get_fdata()
    return img_array

def load_jpeg_png(file_path):
    """ Load JPEG/PNG (any Pillow-supported format) and return NumPy array """
    # Convert to grayscale for a consistent pipeline
    with Image.open(file_path).convert("L") as img:
        return np.array(img, dtype=np.float32)
