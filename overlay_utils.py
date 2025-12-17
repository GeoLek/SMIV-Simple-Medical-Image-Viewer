# overlay_utils.py

import os
import numpy as np
import nibabel as nib
from PIL import Image
import cv2
import json


SUPPORTED_MASK_EXTS = {".nii", ".gz", ".nii.gz", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".npy"}


def load_label_names_for_mask(mask_path: str):
    """
    Try to load human-readable label names for a mask from a sidecar JSON.

    Supported sidecars (checked in this order):
      1) <mask_path>.labels.json     (e.g. mask.nii.gz.labels.json)
      2) <mask_stem>.labels.json     (e.g. mask.labels.json)
      3) <mask_stem>.json            (e.g. mask.json)

    Expected JSON formats (either is fine):
      A) {"1": "liver", "2": "pancreas"}
      B) {"labels": {"1": "liver", "2": "pancreas"}}

    Returns:
      dict[int, str] or {} if not found/invalid.
    """
    candidates = []

    # 1) mask.nii.gz.labels.json
    candidates.append(mask_path + ".labels.json")

    # build stem safely for .nii.gz
    p = mask_path
    if p.lower().endswith(".nii.gz"):
        stem = p[:-7]
    else:
        stem = os.path.splitext(p)[0]

    # 2) mask.labels.json
    candidates.append(stem + ".labels.json")
    # 3) mask.json
    candidates.append(stem + ".json")

    for js in candidates:
        if not os.path.exists(js):
            continue
        try:
            with open(js, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, dict) and "labels" in data and isinstance(data["labels"], dict):
                data = data["labels"]

            if not isinstance(data, dict):
                continue

            out = {}
            for k, v in data.items():
                try:
                    kk = int(k)
                except Exception:
                    continue
                if isinstance(v, str) and v.strip():
                    out[kk] = v.strip()
            return out
        except Exception:
            continue

    return {}

def _lower_ext(path: str) -> str:
    p = path.lower()
    if p.endswith(".nii.gz"):
        return ".nii.gz"
    return os.path.splitext(p)[1]


def load_mask(mask_path: str) -> np.ndarray:
    """
    Load a segmentation mask from:
      - NIfTI (.nii, .nii.gz): returns float array
      - PNG/JPG/TIFF: returns uint8 2D array (grayscale)
      - NPY: returns numpy array as-is

    Returns:
      mask array as np.ndarray
    """
    ext = _lower_ext(mask_path)

    if ext in [".nii", ".nii.gz"]:
        m = nib.load(mask_path).get_fdata()
        return np.asarray(m)

    if ext == ".npy":
        m = np.load(mask_path)
        return np.asarray(m)

    if ext in [".png", ".jpg", ".jpeg", ".tif", ".tiff"]:
        with Image.open(mask_path) as img:
            img = img.convert("L")
            arr = np.array(img, dtype=np.uint8)
        return arr

    raise ValueError(f"Unsupported mask format: {mask_path}")


def get_mask_slice(mask_vol: np.ndarray, z_index: int = 0, t_index: int = 0) -> np.ndarray:
    """
    Extract a 2D mask slice from possible mask shapes:
      - (H, W)
      - (H, W, Z)
      - (H, W, Z, T)

    If mask is smaller than requested indices, indices are clamped.

    Returns:
      2D mask array (H, W)
    """
    if mask_vol is None:
        return None

    m = np.asarray(mask_vol)

    if m.ndim == 2:
        return m

    if m.ndim == 3:
        z = int(np.clip(z_index, 0, m.shape[2] - 1))
        return m[..., z]

    if m.ndim == 4:
        z = int(np.clip(z_index, 0, m.shape[2] - 1))
        t = int(np.clip(t_index, 0, m.shape[3] - 1))
        return m[..., z, t]

    # Unknown shape; try to squeeze down
    m2 = np.squeeze(m)
    if m2.ndim == 2:
        return m2
    raise ValueError(f"Unsupported mask shape: {m.shape}")


def to_binary_mask(mask2d: np.ndarray, threshold: float = 0.0) -> np.ndarray:
    """
    Convert a 2D mask to binary (0/1).
    Default: anything > 0 becomes 1.
    """
    if mask2d is None:
        return None

    m = np.asarray(mask2d)

    # Handle NaNs
    m = np.nan_to_num(m)

    # If mask is already uint8, treat >0 as foreground
    bin_m = (m > threshold).astype(np.uint8)
    return bin_m


def resize_mask_nearest(mask2d: np.ndarray, target_w: int, target_h: int) -> np.ndarray:
    """
    Resize mask using nearest neighbor (critical for segmentation masks).
    Returns uint8 0/1 mask.
    """
    if mask2d is None:
        return None

    m = np.asarray(mask2d).astype(np.uint8)
    resized = cv2.resize(m, (int(target_w), int(target_h)), interpolation=cv2.INTER_NEAREST)
    return resized.astype(np.uint8)


def apply_overlay_to_pil(
    base_pil: Image.Image,
    mask2d_binary: np.ndarray,
    alpha: float = 0.35,
    color_rgb=(255, 0, 0),
) -> Image.Image:
    """
    Alpha blend a solid color overlay on top of base_pil where mask == 1.

    base_pil:
      - PIL.Image, mode "L" or "RGB"
    mask2d_binary:
      - 2D uint8 array (0/1) same width/height as base_pil

    alpha:
      - 0.0..1.0

    color_rgb:
      - overlay color tuple

    Returns:
      PIL.Image in RGB mode
    """
    if base_pil is None or mask2d_binary is None:
        return base_pil

    alpha = float(alpha)
    alpha = max(0.0, min(1.0, alpha))

    # Ensure RGB output
    if base_pil.mode != "RGB":
        base_rgb = base_pil.convert("RGB")
    else:
        base_rgb = base_pil

    base_arr = np.array(base_rgb, dtype=np.float32)  # (H, W, 3)
    mask = (mask2d_binary > 0)

    if mask.ndim != 2:
        raise ValueError(f"mask2d_binary must be 2D, got shape {mask2d_binary.shape}")

    if base_arr.shape[0] != mask.shape[0] or base_arr.shape[1] != mask.shape[1]:
        raise ValueError(
            f"Mask size {mask.shape[::-1]} does not match image size {(base_arr.shape[1], base_arr.shape[0])}"
        )

    overlay = np.zeros_like(base_arr)
    overlay[:, :, 0] = float(color_rgb[0])
    overlay[:, :, 1] = float(color_rgb[1])
    overlay[:, :, 2] = float(color_rgb[2])

    # Blend only where mask is True
    base_arr[mask] = (1.0 - alpha) * base_arr[mask] + alpha * overlay[mask]

    out = np.clip(base_arr, 0, 255).astype(np.uint8)
    return Image.fromarray(out, mode="RGB")

def apply_multiclass_overlay_to_pil(
    base_pil: Image.Image,
    mask2d: np.ndarray,
    label_colors: dict,
    alpha: float = 0.35,
    outline: bool = False,
):
    """
    Apply multi-class overlay. Safe fallback if only label=1 exists.
    """
    if base_pil.mode != "RGB":
        base_pil = base_pil.convert("RGB")

    base = np.array(base_pil, dtype=np.float32)
    mask2d = np.asarray(mask2d)

    for lbl, color in label_colors.items():
        if lbl == 0:
            continue

        region = (mask2d == lbl)
        if not np.any(region):
            continue

        if outline:
            edges = cv2.Canny(region.astype(np.uint8) * 255, 50, 150)
            region = edges > 0

        base[region] = (1 - alpha) * base[region] + alpha * np.array(color)

    return Image.fromarray(np.clip(base, 0, 255).astype(np.uint8))


def default_label_colormap(mask_vol: np.ndarray):
    """
    Create a deterministic color map for labels found in the mask.
    Label 0 is ignored (background).
    """
    if mask_vol is None:
        return {}

    labels = np.unique(mask_vol)
    labels = labels[labels != 0]

    # Simple repeating color palette (safe & readable)
    palette = [
        (255, 0, 0),
        (0, 255, 0),
        (0, 0, 255),
        (255, 255, 0),
        (255, 0, 255),
        (0, 255, 255),
        (255, 128, 0),
        (128, 0, 255),
    ]

    color_map = {}
    for i, lbl in enumerate(labels):
        color_map[int(lbl)] = palette[i % len(palette)]

    return color_map
