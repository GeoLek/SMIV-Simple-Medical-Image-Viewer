#image_loader.py
import os
import pydicom
import nibabel as nib
import numpy as np
from PIL import Image

def detect_file_type_and_metadata(file_path):
    """
    Detects whether a file is DICOM, NIfTI, JPEG/PNG, or unknown.
    Works even if the file has NO EXTENSION.
    """
    # 1) Try to read as DICOM (even without .dcm extension)
    try:
        dcm_data = pydicom.dcmread(file_path, stop_before_pixels=False, force=True)
        if dcm_data:
            shape = dcm_data.pixel_array.shape
            shape_info = f"Shape: {shape}\n"
            if len(shape) == 2:
                shape_info += " => 2D DICOM\n"
            elif len(shape) == 3:
                shape_info += " => Possibly multi-frame or 3D DICOM\n"

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
        pass  # Not a valid DICOM file

    # 2) Try to read as NIfTI
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

    # 3) Try to read as PNG/JPG
    try:
        with Image.open(file_path) as img:
            img.verify()  # If no error, it's a valid image
        meta_str = "===== JPEG/PNG Info =====\n2D standard image.\n=========================\n"
        return "JPEG/PNG", meta_str
    except Exception:
        pass

    return None, "Error: Unknown or unsupported file format."


def detect_file_type(file_path):
    """
    Detects only the file type (DICOM, NIfTI, JPEG/PNG) for use in viewer_3d.
    """
    file_type, _ = detect_file_type_and_metadata(file_path)
    return file_type

def load_dicom(file_path):
    """ Load DICOM image, normalize to [0..255], and return a NumPy array. """
    dicom_data = pydicom.dcmread(file_path, force=True)
    img_array = dicom_data.pixel_array.astype(np.float32)

    # Normalize image to range [0, 255]
    min_val, max_val = img_array.min(), img_array.max()
    if max_val != min_val:
        img_array = (img_array - min_val) / (max_val - min_val) * 255
    return img_array

def load_nifti(file_path):
    """ Load NIfTI image (2D, 3D, or 4D) and return a NumPy array. """
    nii_data = nib.load(file_path)
    img_array = nii_data.get_fdata()
    return img_array

def load_jpeg_png(file_path):
    """ Load PNG/JPEG in grayscale format. """
    with Image.open(file_path).convert("L") as img:
        return np.array(img, dtype=np.float32)
