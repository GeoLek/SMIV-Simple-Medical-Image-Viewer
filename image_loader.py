# image_loader.py

import os
import warnings
import pydicom
import nibabel as nib
import numpy as np
from PIL import Image, ImageFile
import math

warnings.filterwarnings("ignore", category=UserWarning, module="pydicom")
warnings.simplefilter("ignore", Image.DecompressionBombWarning)
Image.MAX_IMAGE_PIXELS = None  # allow very large images

# Try OpenSlide for WSI formats (.svs, .scn, .ndpi, etc.)
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

    # 5) Final fallback: try OpenSlide again as generic WSI check
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

def get_dicom_series_uid(file_path):
    """
    Fast header-only read to get SeriesInstanceUID.
    Returns None if not readable or missing.
    """
    try:
        ds = pydicom.dcmread(file_path, stop_before_pixels=True, force=True)
        return str(getattr(ds, "SeriesInstanceUID", None)) if getattr(ds, "SeriesInstanceUID", None) else None
    except Exception:
        return None


def _dicom_has_pixels(ds) -> bool:
    """
    Some DICOMs (RTSTRUCT, SEG objects, etc.) may not have PixelData.
    """
    try:
        return hasattr(ds, "PixelData")
    except Exception:
        return False


def _safe_float(x, default=None):
    try:
        return float(x)
    except Exception:
        return default


def _safe_int(x, default=None):
    try:
        return int(x)
    except Exception:
        return default


def _series_sort_key(ds, fallback_name=""):
    """
    Sort slices robustly:
    1) Use ImagePositionPatient projected on slice normal if IOP/IPP exist
    2) Else SliceLocation
    3) Else InstanceNumber
    4) Else filename fallback
    """
    # Best: IPP + IOP
    try:
        ipp = getattr(ds, "ImagePositionPatient", None)
        iop = getattr(ds, "ImageOrientationPatient", None)
        if ipp is not None and iop is not None and len(ipp) == 3 and len(iop) == 6:
            rx, ry, rz = float(iop[0]), float(iop[1]), float(iop[2])
            cx, cy, cz = float(iop[3]), float(iop[4]), float(iop[5])

            # normal = row x col
            nx = ry * cz - rz * cy
            ny = rz * cx - rx * cz
            nz = rx * cy - ry * cx

            px, py, pz = float(ipp[0]), float(ipp[1]), float(ipp[2])
            loc = px * nx + py * ny + pz * nz
            return (0, loc)
    except Exception:
        pass

    # Fallback: SliceLocation
    sl = _safe_float(getattr(ds, "SliceLocation", None), default=None)
    if sl is not None:
        return (1, sl)

    # Fallback: InstanceNumber
    inst = _safe_int(getattr(ds, "InstanceNumber", None), default=None)
    if inst is not None:
        return (2, inst)

    # Final: name
    return (3, fallback_name)


def load_dicom_series_from_file(file_path):
    """
    Load a DICOM *series* based on the selected file:
      - Finds SeriesInstanceUID of selected file
      - Collects all matching DICOM slices in the same folder
      - Sorts them
      - Loads pixel arrays, applies RescaleSlope/Intercept
      - Returns a stacked volume: (H, W, Z) float32

    Returns:
      volume_3d, meta_str, meta_dict
    """
    folder = os.path.dirname(file_path)

    # Read the reference file header
    try:
        ref = pydicom.dcmread(file_path, stop_before_pixels=True, force=True)
    except Exception as e:
        raise RuntimeError(f"Failed to read DICOM header: {e}")

    series_uid = getattr(ref, "SeriesInstanceUID", None)
    if not series_uid:
        # If no SeriesInstanceUID, fallback to single-file load
        ds = pydicom.dcmread(file_path, force=True)
        arr = ds.pixel_array.astype(np.float32)
        slope = _safe_float(getattr(ds, "RescaleSlope", 1.0), 1.0)
        intercept = _safe_float(getattr(ds, "RescaleIntercept", 0.0), 0.0)
        arr = arr * slope + intercept
        vol = arr[..., np.newaxis]  # (H,W,1)
        meta = {
            "SeriesInstanceUID": None,
            "PixelSpacing": getattr(ds, "PixelSpacing", None),
            "RescaleSlope": slope,
            "RescaleIntercept": intercept,
            "Modality": getattr(ds, "Modality", None),
        }
        meta_str = (
            "===== DICOM (single file) =====\n"
            f"File: {os.path.basename(file_path)}\n"
            f"Shape: {arr.shape}\n"
            f"Slope/Intercept: {slope}, {intercept}\n"
            "===============================\n"
        )
        return vol.astype(np.float32), meta_str, meta

    # If this is multi-frame DICOM, handle it as a volume without scanning folder
    try:
        nframes = _safe_int(getattr(ref, "NumberOfFrames", None), default=1)
    except Exception:
        nframes = 1

    if nframes and nframes > 1:
        ds = pydicom.dcmread(file_path, force=True)
        arr = ds.pixel_array.astype(np.float32)  # typically (frames, H, W)
        if arr.ndim == 3:
            arr = np.moveaxis(arr, 0, -1)  # -> (H, W, frames)
        slope = _safe_float(getattr(ds, "RescaleSlope", 1.0), 1.0)
        intercept = _safe_float(getattr(ds, "RescaleIntercept", 0.0), 0.0)
        arr = arr * slope + intercept

        meta = {
            "SeriesInstanceUID": str(series_uid),
            "PixelSpacing": getattr(ds, "PixelSpacing", None),
            "RescaleSlope": slope,
            "RescaleIntercept": intercept,
            "Modality": getattr(ds, "Modality", None),
            "NumberOfFrames": nframes,
        }
        meta_str = (
            "===== DICOM Multi-frame =====\n"
            f"SeriesInstanceUID: {series_uid}\n"
            f"Frames: {nframes}\n"
            f"Volume shape (H,W,Z): {arr.shape}\n"
            f"Slope/Intercept: {slope}, {intercept}\n"
            "=============================\n"
        )
        return arr.astype(np.float32), meta_str, meta

    # Collect all matching slices in same folder (header-only reads)
    candidates = []
    for name in sorted(os.listdir(folder)):
        p = os.path.join(folder, name)
        if not os.path.isfile(p):
            continue

        try:
            ds_h = pydicom.dcmread(p, stop_before_pixels=True, force=True)
        except Exception:
            continue

        if getattr(ds_h, "SeriesInstanceUID", None) != series_uid:
            continue

        if not hasattr(ds_h, "Rows") or not hasattr(ds_h, "Columns"):
            continue

        candidates.append((p, ds_h))

    if not candidates:
        # Fallback: treat it as a single DICOM file (series scan failed / single file)
        ds = pydicom.dcmread(file_path, force=True)
        arr = ds.pixel_array.astype(np.float32)
        slope = _safe_float(getattr(ds, "RescaleSlope", 1.0), 1.0)
        intercept = _safe_float(getattr(ds, "RescaleIntercept", 0.0), 0.0)
        arr = arr * slope + intercept

        meta = {
            "SeriesInstanceUID": str(series_uid),
            "PixelSpacing": getattr(ds, "PixelSpacing", None),
            "RescaleSlope": slope,
            "RescaleIntercept": intercept,
            "Modality": getattr(ds, "Modality", None),
        }
        meta_str = (
            "===== DICOM (single file fallback) =====\n"
            f"SeriesInstanceUID: {series_uid}\n"
            f"File: {os.path.basename(file_path)}\n"
            f"Shape: {arr.shape}\n"
            f"Slope/Intercept: {slope}, {intercept}\n"
            "=======================================\n"
        )
        vol = arr[..., np.newaxis]  # (H,W,1)
        return vol.astype(np.float32), meta_str, meta

    # Sort slices
    candidates.sort(key=lambda item: _series_sort_key(item[1], os.path.basename(item[0])))

    # Load pixels and stack
    slices = []
    first_shape = None
    first_ds_full = None

    for p, _ds_h in candidates:
        try:
            ds = pydicom.dcmread(p, force=True)
            if not _dicom_has_pixels(ds):
                continue

            arr2d = ds.pixel_array.astype(np.float32)

            # Skip color DICOM for now (can be added later)
            if arr2d.ndim != 2:
                continue

            if first_shape is None:
                first_shape = arr2d.shape
                first_ds_full = ds
            elif arr2d.shape != first_shape:
                # keep stack consistent
                continue

            slope = _safe_float(getattr(ds, "RescaleSlope", 1.0), 1.0)
            intercept = _safe_float(getattr(ds, "RescaleIntercept", 0.0), 0.0)
            arr2d = arr2d * slope + intercept

            # Handle MONOCHROME1 inversion (optional but common)
            pi = getattr(ds, "PhotometricInterpretation", "")
            if isinstance(pi, str) and pi.strip().upper() == "MONOCHROME1":
                arr2d = np.max(arr2d) - arr2d

            slices.append(arr2d)
        except Exception:
            continue

    if not slices:
        raise RuntimeError("Failed to load any slice pixel data for this series.")

    vol = np.stack(slices, axis=-1).astype(np.float32)  # (H, W, Z)

    # meta
    ps = getattr(first_ds_full, "PixelSpacing", None) if first_ds_full is not None else None
    slope0 = _safe_float(getattr(first_ds_full, "RescaleSlope", 1.0), 1.0) if first_ds_full is not None else 1.0
    intercept0 = _safe_float(getattr(first_ds_full, "RescaleIntercept", 0.0), 0.0) if first_ds_full is not None else 0.0
    modality = getattr(first_ds_full, "Modality", None) if first_ds_full is not None else None

    meta = {
        "SeriesInstanceUID": str(series_uid),
        "PixelSpacing": ps,
        "RescaleSlope": slope0,
        "RescaleIntercept": intercept0,
        "Modality": modality,
        "NumSlices": int(vol.shape[-1]),
    }

    meta_str = (
        "===== DICOM Series =====\n"
        f"SeriesInstanceUID: {series_uid}\n"
        f"Slices: {vol.shape[-1]}\n"
        f"Slice shape: {vol.shape[0]} x {vol.shape[1]}\n"
        f"Volume shape (H,W,Z): {vol.shape}\n"
        f"PixelSpacing: {ps}\n"
        f"Slope/Intercept: {slope0}, {intercept0}\n"
        "========================\n"
    )

    return vol, meta_str, meta

def load_dicom_auto(file_path):
    """
    Try loading a DICOM series (stack) first, then fallback to single-file DICOM.
    """
    try:
        if "load_dicom_series" in globals():
            return load_dicom_series_from_file(file_path)
    except Exception as e:
        print(f"[WARN] load_dicom_series failed, fallback to single: {e}")

    return load_dicom(file_path)

def load_whole_slide_downsampled(file_path, max_dim=2048):
    """
    Use OpenSlide to load a downsampled overview image of a WSI.
    We pick the lowest-resolution level whose max dimension <= max_dim.
    If none fit, we take the lowest level (highest index).
    Returns a 2D float32 array (grayscale).
    """
    import openslide
    slide = openslide.OpenSlide(file_path)

    # Choose a level such that max(w, h) <= max_dim if possible
    chosen_level = slide.level_count - 1  # start from lowest resolution
    for lvl in range(slide.level_count - 1, -1, -1):
        w, h = slide.level_dimensions[lvl]
        if max(w, h) <= max_dim:
            chosen_level = lvl
            break

    w, h = slide.level_dimensions[chosen_level]
    print(f"[DEBUG] load_whole_slide_downsampled: using level {chosen_level} with size {w}x{h}")
    rgba = slide.read_region((0, 0), chosen_level, (w, h))
    arr = rgba.convert("L")  # or "RGB" for color
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
    """
    Load PNG/JPEG preserving color if present.
    Returns:
      - (H, W) float32 for grayscale
      - (H, W, 3) float32 for RGB
    """
    with Image.open(file_path) as img:
        # Normalize modes; keep RGB if it’s color
        if img.mode in ("RGB", "RGBA", "P"):
            img = img.convert("RGB")
            return np.array(img, dtype=np.float32)
        else:
            img = img.convert("L")
            return np.array(img, dtype=np.float32)


def load_tiff(file_path):
    """
    Minimal load for TIFF. Only the first page.
    Preserve RGB if present.
    """
    with Image.open(file_path) as img:
        if img.mode in ("RGB", "RGBA", "P"):
            arr = img.convert("RGB")
        else:
            arr = img.convert("L")
    return np.array(arr, dtype=np.float32)


def load_any_image(file_path, file_type):
    """
    Single router function – if you want to unify calls in your code.
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
        return load_whole_slide_downsampled(file_path, max_dim=2048)
    else:
        return None
