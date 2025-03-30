# image_loader.py

import os
import warnings

import pydicom
import nibabel as nib
import numpy as np
from PIL import Image, ImageFile

warnings.filterwarnings("ignore", category=UserWarning, module="pydicom")
warnings.simplefilter("ignore", Image.DecompressionBombWarning)
Image.MAX_IMAGE_PIXELS = None

# Attempt to import OpenSlide
try:
    import openslide
    OPENSLIDE_AVAILABLE = True
except ImportError:
    openslide = None
    OPENSLIDE_AVAILABLE = False


def detect_file_type_and_metadata(file_path):
    """
    Detect if a file is:
      - DICOM
      - NIfTI
      - JPEG/PNG
      - TIFF
      - WHOLESLIDE (.svs, .scn, etc. via OpenSlide)
      or unknown.
    """
    print("\nLoading... Please wait while we identify the file type.")
    print(f"[DEBUG] Checking file: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()

    # 1) If extension suggests a WSI, try OpenSlide first
    if OPENSLIDE_AVAILABLE and ext in [".svs", ".scn", ".mrxs", ".ndpi", ".vms", ".bif"]:
        print("[DEBUG] Attempting OpenSlide read by extension:", ext)
        try:
            slide = openslide.OpenSlide(file_path)
            dims = slide.dimensions
            print("[DEBUG] OpenSlide => success!")
            meta_str = (
                "===== Whole Slide Image =====\n"
                f"Dimensions: {dims}\n"
                f"Levels: {slide.level_count}\n"
                f"Level Dimensions: {slide.level_dimensions}\n"
                f"Vendor: {slide.properties.get('openslide.vendor', 'Unknown')}\n"
                "=============================\n"
            )
            return "WHOLESLIDE", meta_str
        except Exception as e:
            print(f"[DEBUG] OpenSlide read by extension failed: {e}")

    # 2) Try DICOM
    try:
        print("[DEBUG] Attempting DICOM read...")
        dcm_data = pydicom.dcmread(file_path, stop_before_pixels=False, force=True)
        if dcm_data:
            shape = dcm_data.pixel_array.shape
            print("[DEBUG] DICOM read success!")
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
    except Exception as e:
        print(f"[DEBUG] DICOM read failed: {e}")

    # 3) Try NIfTI
    try:
        print("[DEBUG] Attempting NIfTI read...")
        nii = nib.load(file_path)
        if nii:
            shape = nii.shape
            print("[DEBUG] NIfTI read success!")
            shape_info = f"Shape: {shape}\n => {len(shape)}D NIfTI\n"
            hdr = nii.header
            meta_str = (
                "===== NIfTI Info =====\n"
                f"{hdr}\n"
                f"{shape_info}"
                "======================\n"
            )
            return "NIfTI", meta_str
    except Exception as e:
        print(f"[DEBUG] NIfTI read failed: {e}")

    # 4) Try Pillow => PNG/JPG/TIFF
    try:
        print("[DEBUG] Attempting Pillow read (PNG/JPG/TIFF)...")
        with Image.open(file_path) as img:
            img_format = img.format
            img.verify()
        if img_format in ["JPEG", "PNG"]:
            print("[DEBUG] Pillow => JPEG/PNG success.")
            meta_str = (
                "===== JPEG/PNG Info =====\n"
                "2D standard image.\n"
                "=========================\n"
            )
            return "JPEG/PNG", meta_str
        elif img_format == "TIFF":
            print("[DEBUG] Pillow => TIFF success.")
            meta_str = (
                "===== TIFF Info =====\n"
                "Possibly multi-page or single-page.\n"
                "=========================\n"
            )
            return "TIFF", meta_str
    except Exception as e:
        print(f"[DEBUG] Pillow read failed: {e}")

    # 5) Final fallback: try OpenSlide anyway
    if OPENSLIDE_AVAILABLE:
        print("[DEBUG] Checking with OpenSlide fallback for WSI.")
        try:
            slide = openslide.OpenSlide(file_path)
            dims = slide.dimensions
            print("[DEBUG] OpenSlide => success (fallback).")
            meta_str = (
                "===== Whole Slide Image =====\n"
                f"Dimensions: {dims}\n"
                f"Levels: {slide.level_count}\n"
                f"Level Dimensions: {slide.level_dimensions}\n"
                f"Vendor: {slide.properties.get('openslide.vendor', 'Unknown')}\n"
                "=============================\n"
            )
            return "WHOLESLIDE", meta_str
        except Exception as e:
            print(f"[DEBUG] OpenSlide fallback failed: {e}")

    print("[DEBUG] => Unknown format. Returning None.")
    return None, "Error: Unknown or unsupported file format."


def load_whole_slide(file_path):
    """
    This version ALWAYS picks the highest level (smallest dimension)
    AND attempts to respect bounding box (if available).
    So we see the entire tissue at once, downsampled.
    """
    if not OPENSLIDE_AVAILABLE:
        return None

    import openslide
    slide = openslide.OpenSlide(file_path)
    level_count = slide.level_count
    highest_level = level_count - 1  # the smallest dimension

    # The dimension at that level
    w_full, h_full = slide.level_dimensions[highest_level]

    # If bounding props exist, use them
    bounds_x = int(slide.properties.get('openslide.bounds-x', 0))
    bounds_y = int(slide.properties.get('openslide.bounds-y', 0))
    if 'openslide.bounds-width' in slide.properties:
        w_full = int(slide.properties['openslide.bounds-width'])
    if 'openslide.bounds-height' in slide.properties:
        h_full = int(slide.properties['openslide.bounds-height'])

    region = slide.read_region((bounds_x, bounds_y), highest_level, (w_full, h_full))
    arr = region.convert("L")  # or "RGB" if you want color
    return np.array(arr, dtype=np.float32)


def detect_file_type(file_path):
    """Return the file type only."""
    ft, _ = detect_file_type_and_metadata(file_path)
    return ft


def load_dicom(file_path):
    """Load DICOM => [0..255] float32."""
    dicom_data = pydicom.dcmread(file_path, force=True)
    img_array = dicom_data.pixel_array.astype(np.float32)
    min_val, max_val = img_array.min(), img_array.max()
    if max_val != min_val:
        img_array = (img_array - min_val) / (max_val - min_val) * 255
    return img_array


def load_nifti(file_path):
    """Load NIfTI => float64 array."""
    nii_data = nib.load(file_path)
    return nii_data.get_fdata()


def load_jpeg_png(file_path):
    """Load PNG/JPEG => grayscale float32 [0..255]."""
    with Image.open(file_path).convert("L") as img:
        return np.array(img, dtype=np.float32)


def load_tiff(file_path):
    """Minimal load for TIFF. Only the first page in grayscale."""
    with Image.open(file_path) as img:
        arr = img.convert("L")
    return np.array(arr, dtype=np.float32)


def load_any_image(file_path, file_type):
    """
    Single router function to unify calls in your code.
    """
    if file_type == "DICOM":
        return load_dicom(file_path)
    elif file_type == "NIfTI":
        return load_nifti(file_path)
    elif file_type == "JPEG/PNG":
        return load_jpeg_png(file_path)
    elif file_type == "TIFF":
        return load_tiff(file_path)
    elif file_type == "WHOLESLIDE":
        # Use the bounding-based downsample approach
        return load_whole_slide(file_path)
    else:
        return None
