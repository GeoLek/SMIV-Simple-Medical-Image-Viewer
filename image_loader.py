# image_loader.py

import pydicom
import nibabel as nib
import numpy as np
from PIL import Image

def detect_file_type_and_metadata(file_path):
    """
    Detect whether a file is DICOM, NIfTI, or JPEG/PNG,
    and return (file_type, metadata_str).
    metadata_str is a summary of dimension/header info.
    """
    # 1) Try DICOM
    try:
        dcm_data = pydicom.dcmread(file_path, stop_before_pixels=False)
        if dcm_data:
            shape = dcm_data.pixel_array.shape
            shape_info = f"Shape: {shape}\n"
            if len(shape) == 2:
                shape_info += " => 2D DICOM\n"
            elif len(shape) == 3:
                shape_info += " => Multi-frame or 3D DICOM\n"

            meta_str = (
                "===== DICOM Info =====\n"
                f"Patient Name: {dcm_data.get('PatientName', 'Unknown')}\n"
                f"Study ID: {dcm_data.get('StudyID', 'N/A')}\n"
                f"Modality: {dcm_data.get('Modality', 'N/A')}\n"
                + shape_info +
                "=======================\n"
            )
            return "DICOM", meta_str
    except Exception:
        pass

    # 2) Try NIfTI
    try:
        nii_data = nib.load(file_path)
        if nii_data:
            shape = nii_data.shape
            shape_info = f"Shape: {shape}\n => {len(shape)}D NIfTI\n"
            hdr = nii_data.header
            meta_str = (
                "===== NIfTI Info =====\n"
                f"{hdr}\n"
                f"{shape_info}"
                "======================\n"
            )
            return "NIfTI", meta_str
    except Exception:
        pass

    # 3) Try JPEG/PNG
    try:
        with Image.open(file_path) as img:
            img.verify()  # If no error => valid image
        meta_str = "===== JPEG/PNG Info =====\n2D standard image.\n=========================\n"
        return "JPEG/PNG", meta_str
    except Exception:
        pass

    return None, "Error: Unknown or unsupported file format."

def load_dicom(file_path):
    """ Load DICOM image and return normalized NumPy array [0..255] in float32. """
    dicom_data = pydicom.dcmread(file_path)
    img_array = dicom_data.pixel_array.astype(np.float32)
    min_val, max_val = img_array.min(), img_array.max()
    if max_val != min_val:
        img_array = (img_array - min_val) / (max_val - min_val) * 255
    return img_array

def load_nifti(file_path):
    """ Load NIfTI image (2D, 3D, or 4D) and return float64 array. """
    nii_data = nib.load(file_path)
    img_array = nii_data.get_fdata()
    return img_array

def load_jpeg_png(file_path):
    """ Load JPEG/PNG in grayscale [0..255] float32. """
    with Image.open(file_path).convert("L") as img:
        return np.array(img, dtype=np.float32)
