# image_loader.py

import os
import warnings
import json
import numpy as np
import pydicom
import nibabel as nib
from PIL import Image, ImageFile

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


# ---------------------------------------------------------
# Small helpers
# ---------------------------------------------------------
def _safe_float(x, default=0.0) -> float:
    try:
        # pydicom MultiValue / list => take first element
        if isinstance(x, (list, tuple)) and len(x) > 0:
            x = x[0]
        return float(x)
    except Exception:
        return float(default)

def _safe_int(x, default=0) -> int:
    try:
        if isinstance(x, (list, tuple)) and len(x) > 0:
            x = x[0]
        return int(x)
    except Exception:
        return int(default)

def _dicom_has_pixels(ds) -> bool:
    try:
        return hasattr(ds, "PixelData") and ds.get("Rows", None) is not None and ds.get("Columns", None) is not None
    except Exception:
        return False

def _series_sort_key(ds_h, filename_fallback=""):
    """
    Robust sorting for DICOM series.
    Priority:
      1) ImagePositionPatient (z)
      2) InstanceNumber
      3) SliceLocation
      4) filename
    """
    z = None
    try:
        ipp = getattr(ds_h, "ImagePositionPatient", None)
        if ipp is not None and len(ipp) >= 3:
            z = float(ipp[2])
    except Exception:
        z = None

    inst = _safe_int(getattr(ds_h, "InstanceNumber", None), default=10**9)
    sl = _safe_float(getattr(ds_h, "SliceLocation", None), default=0.0)

    # Put None z at the end
    z_key = (0, z) if z is not None else (1, 0.0)
    return (z_key, inst, sl, filename_fallback)


# ---------------------------------------------------------
# File type detection + metadata string
# ---------------------------------------------------------
def detect_file_type_and_metadata(file_path):
    """
    Detect if a file is:
      - DICOM
      - NIfTI
      - JPEG/PNG
      - TIFF
      - WHOLESLIDE (.svs, .scn, etc. via OpenSlide)
      or unknown.
    Returns: (file_type, meta_str)
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

    # 2) Try DICOM (header + pixels, because some files lie)
    try:
        print("[DEBUG] Attempting DICOM read...")
        ds = pydicom.dcmread(file_path, stop_before_pixels=False, force=True)
        if ds and _dicom_has_pixels(ds):
            # pixel_array access can throw; guard it
            try:
                shape = ds.pixel_array.shape
            except Exception:
                shape = ("?", "?")
            meta_str = (
                "===== DICOM Info =====\n"
                f"Patient Name: {ds.get('PatientName', 'Unknown')}\n"
                f"Study ID: {ds.get('StudyID', 'N/A')}\n"
                f"Modality: {ds.get('Modality', 'N/A')}\n"
                f"SeriesInstanceUID: {getattr(ds, 'SeriesInstanceUID', 'N/A')}\n"
                f"Shape: {shape}\n"
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
            hdr = nii.header
            meta_str = (
                "===== NIfTI Info =====\n"
                f"{hdr}\n"
                f"Shape: {shape}\n"
                f"Dim: {len(shape)}D\n"
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
            meta_str = (
                "===== JPEG/PNG Info =====\n"
                "2D standard image.\n"
                "=========================\n"
            )
            return "JPEG/PNG", meta_str
        elif img_format == "TIFF":
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

    return None, "Error: Unknown or unsupported file format."


def detect_file_type(file_path):
    ft, _ = detect_file_type_and_metadata(file_path)
    return ft


# ---------------------------------------------------------
# WSI loader
# ---------------------------------------------------------
def load_whole_slide_downsampled(file_path, max_dim=2048):
    """
    Use OpenSlide to load a downsampled overview image of a WSI.
    Pick lowest-res level whose max dimension <= max_dim if possible.
    Returns a 2D float32 array (grayscale).
    """
    import openslide
    slide = openslide.OpenSlide(file_path)

    chosen_level = slide.level_count - 1
    for lvl in range(slide.level_count - 1, -1, -1):
        w, h = slide.level_dimensions[lvl]
        if max(w, h) <= max_dim:
            chosen_level = lvl
            break

    w, h = slide.level_dimensions[chosen_level]
    print(f"[DEBUG] load_whole_slide_downsampled: using level {chosen_level} with size {w}x{h}")
    rgba = slide.read_region((0, 0), chosen_level, (w, h))
    arr = rgba.convert("L")
    return np.array(arr, dtype=np.float32)


# ---------------------------------------------------------
# Basic image loaders
# ---------------------------------------------------------
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
        if img.mode in ("RGB", "RGBA", "P"):
            img = img.convert("RGB")
            return np.array(img, dtype=np.float32)
        img = img.convert("L")
        return np.array(img, dtype=np.float32)

def load_tiff(file_path):
    """Minimal load for TIFF (first page). Preserve RGB if present."""
    with Image.open(file_path) as img:
        if img.mode in ("RGB", "RGBA", "P"):
            arr = img.convert("RGB")
        else:
            arr = img.convert("L")
    return np.array(arr, dtype=np.float32)


# ---------------------------------------------------------
# DICOM: series stacking with safe fallback
# ---------------------------------------------------------
def load_dicom_series_from_file(file_path):
    """
    Load a DICOM series based on the selected file.
    If it cannot form a series, falls back to single-file.

    Returns:
      volume_3d (H,W,Z) float32 in HU-like units if slope/intercept exist,
      meta_str,
      meta_dict
    """
    folder = os.path.dirname(file_path)

    # Read reference header
    try:
        ref = pydicom.dcmread(file_path, stop_before_pixels=True, force=True)
    except Exception as e:
        raise RuntimeError(f"Failed to read DICOM header: {e}")

    series_uid = getattr(ref, "SeriesInstanceUID", None)

    # If no SeriesInstanceUID => single-file
    if not series_uid:
        return _load_dicom_single_as_volume(file_path, note="DICOM (single file)")

    # Multi-frame? load directly without scanning folder
    nframes = _safe_int(getattr(ref, "NumberOfFrames", None), default=1)
    if nframes and nframes > 1:
        ds = pydicom.dcmread(file_path, force=True)
        if not _dicom_has_pixels(ds):
            return _load_dicom_single_as_volume(file_path, note="DICOM (single file)")
        arr = ds.pixel_array.astype(np.float32)
        if arr.ndim == 3:
            # (frames,H,W) -> (H,W,frames)
            arr = np.moveaxis(arr, 0, -1)

        slope = _safe_float(getattr(ds, "RescaleSlope", 1.0), 1.0)
        intercept = _safe_float(getattr(ds, "RescaleIntercept", 0.0), 0.0)
        arr = arr * slope + intercept

        pi = getattr(ds, "PhotometricInterpretation", "")
        if isinstance(pi, str) and pi.strip().upper() == "MONOCHROME1":
            arr = np.max(arr) - arr

        meta = _dicom_meta_from_ds(ds)
        meta["SeriesInstanceUID"] = str(series_uid)
        meta["NumberOfFrames"] = int(nframes)

        meta_str = (
            "===== DICOM Multi-frame =====\n"
            f"SeriesInstanceUID: {series_uid}\n"
            f"Frames: {nframes}\n"
            f"Volume shape (H,W,Z): {arr.shape}\n"
            f"Modality: {meta.get('Modality')}\n"
            f"Slope/Intercept: {meta.get('RescaleSlope')}, {meta.get('RescaleIntercept')}\n"
            "=============================\n"
        )
        return arr.astype(np.float32), meta_str, meta

    # Collect slices in folder matching SeriesInstanceUID
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
        # keep only things that *look* like image slices
        if getattr(ds_h, "Rows", None) is None or getattr(ds_h, "Columns", None) is None:
            continue
        candidates.append((p, ds_h))

    # If we cannot find a stack, fallback to single-file
    if len(candidates) < 2:
        return _load_dicom_single_as_volume(file_path, note="DICOM (single file)")

    # Sort slices
    candidates.sort(key=lambda item: _series_sort_key(item[1], os.path.basename(item[0])))

    slices = []
    first_shape = None
    first_ds_full = None

    for p, _ds_h in candidates:
        try:
            ds = pydicom.dcmread(p, force=True)
            if not _dicom_has_pixels(ds):
                continue
            arr2d = ds.pixel_array.astype(np.float32)

            # Skip non-2D slices for now
            if arr2d.ndim != 2:
                continue

            if first_shape is None:
                first_shape = arr2d.shape
                first_ds_full = ds
            elif arr2d.shape != first_shape:
                # Keep stack consistent
                continue

            slope = _safe_float(getattr(ds, "RescaleSlope", 1.0), 1.0)
            intercept = _safe_float(getattr(ds, "RescaleIntercept", 0.0), 0.0)
            arr2d = arr2d * slope + intercept

            pi = getattr(ds, "PhotometricInterpretation", "")
            if isinstance(pi, str) and pi.strip().upper() == "MONOCHROME1":
                arr2d = np.max(arr2d) - arr2d

            slices.append(arr2d)
        except Exception:
            continue

    # If stacking failed, fallback
    if len(slices) < 1:
        return _load_dicom_single_as_volume(file_path, note="DICOM (single file)")

    vol = np.stack(slices, axis=-1).astype(np.float32)  # (H,W,Z)

    meta = _dicom_meta_from_ds(first_ds_full) if first_ds_full is not None else {}
    meta["SeriesInstanceUID"] = str(series_uid)
    meta["NumSlices"] = int(vol.shape[-1])

    meta_str = (
        "===== DICOM Series =====\n"
        f"SeriesInstanceUID: {series_uid}\n"
        f"Slices: {vol.shape[-1]}\n"
        f"Slice shape: {vol.shape[0]} x {vol.shape[1]}\n"
        f"Volume shape (H,W,Z): {vol.shape}\n"
        f"Modality: {meta.get('Modality')}\n"
        f"PixelSpacing: {meta.get('PixelSpacing')}\n"
        f"WindowCenter/Width: {meta.get('WindowCenter')}, {meta.get('WindowWidth')}\n"
        f"Slope/Intercept: {meta.get('RescaleSlope')}, {meta.get('RescaleIntercept')}\n"
        "========================\n"
    )

    return vol, meta_str, meta


def _dicom_meta_from_ds(ds) -> dict:
    if ds is None:
        return {}
    slope = _safe_float(getattr(ds, "RescaleSlope", 1.0), 1.0)
    intercept = _safe_float(getattr(ds, "RescaleIntercept", 0.0), 0.0)

    wc = getattr(ds, "WindowCenter", None)
    ww = getattr(ds, "WindowWidth", None)

    # Keep as float if possible; if absent, keep None
    wc_f = _safe_float(wc, default=None) if wc is not None else None
    ww_f = _safe_float(ww, default=None) if ww is not None else None

    meta = {
        "Modality": getattr(ds, "Modality", None),
        "PixelSpacing": getattr(ds, "PixelSpacing", None),
        "SliceThickness": getattr(ds, "SliceThickness", None),
        "RescaleSlope": slope,
        "RescaleIntercept": intercept,
        "WindowCenter": wc_f,
        "WindowWidth": ww_f,
        "PhotometricInterpretation": getattr(ds, "PhotometricInterpretation", None),
        "SeriesInstanceUID": getattr(ds, "SeriesInstanceUID", None),
        "StudyInstanceUID": getattr(ds, "StudyInstanceUID", None),
    }
    return meta


def _load_dicom_single_as_volume(file_path, note="DICOM (single file)"):
    ds = pydicom.dcmread(file_path, force=True)
    if not _dicom_has_pixels(ds):
        raise RuntimeError("DICOM has no PixelData to display.")

    arr = ds.pixel_array.astype(np.float32)
    # If it is multi-frame but we arrived here, try to reshape anyway
    if arr.ndim == 3:
        # assume (frames,H,W) -> (H,W,frames)
        arr = np.moveaxis(arr, 0, -1)
        vol = arr.astype(np.float32)
    elif arr.ndim == 2:
        vol = arr[..., np.newaxis].astype(np.float32)
    else:
        # Unsupported for now
        raise RuntimeError(f"Unsupported DICOM pixel array shape: {arr.shape}")

    slope = _safe_float(getattr(ds, "RescaleSlope", 1.0), 1.0)
    intercept = _safe_float(getattr(ds, "RescaleIntercept", 0.0), 0.0)
    vol = vol * slope + intercept

    pi = getattr(ds, "PhotometricInterpretation", "")
    if isinstance(pi, str) and pi.strip().upper() == "MONOCHROME1":
        vol = np.max(vol) - vol

    meta = _dicom_meta_from_ds(ds)
    meta["SeriesInstanceUID"] = getattr(ds, "SeriesInstanceUID", None)

    meta_str = (
        f"===== {note} =====\n"
        f"File: {os.path.basename(file_path)}\n"
        f"Volume shape (H,W,Z): {vol.shape}\n"
        f"Modality: {meta.get('Modality')}\n"
        f"PixelSpacing: {meta.get('PixelSpacing')}\n"
        f"WindowCenter/Width: {meta.get('WindowCenter')}, {meta.get('WindowWidth')}\n"
        f"Slope/Intercept: {meta.get('RescaleSlope')}, {meta.get('RescaleIntercept')}\n"
        "===============================\n"
    )
    return vol.astype(np.float32), meta_str, meta


# Backward-compatible: old API used in older viewer code
def load_dicom(file_path):
    """
    Backward-compatible loader:
      - returns a *2D* float32 display-friendly image for a single DICOM
      - (older code expected 0..255 sometimes)
    Prefer using load_dicom_series_from_file() in the new viewer.
    """
    vol, _meta_str, _meta = load_dicom_series_from_file(file_path)
    # return middle slice as 2D if it is a volume
    if vol.ndim == 3:
        z = vol.shape[-1] // 2
        return vol[..., z].astype(np.float32)
    return vol.astype(np.float32)


def load_any_image(file_path, file_type):
    """
    Single router function – if you want to unify calls in your code.
    """
    if file_type == "DICOM":
        # Prefer series-aware load
        vol, _meta_str, _meta = load_dicom_series_from_file(file_path)
        return vol
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
