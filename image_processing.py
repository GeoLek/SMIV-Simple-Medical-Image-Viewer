# image_processing.py

import numpy as np
import cv2


def apply_histogram_equalization(img_array: np.ndarray) -> np.ndarray:
    """
    Apply histogram equalization to a single-channel (grayscale) image.
    If a 3-channel image is passed, it is first converted to grayscale.
    """
    if img_array.ndim == 3 and img_array.shape[2] == 3:
        # Convert color to grayscale first
        img_gray = cv2.cvtColor(img_array.astype(np.uint8), cv2.COLOR_BGR2GRAY)
    else:
        img_gray = img_array.astype(np.uint8)

    eq = cv2.equalizeHist(img_gray)
    return eq.astype(np.float32)


def apply_colormap(img_array: np.ndarray, colormap: int = cv2.COLORMAP_JET) -> np.ndarray:
    """
    Apply an OpenCV colormap to a single-channel image.
    Output is 3-channel uint8 (H, W, 3).
    """
    img_u8 = np.clip(img_array, 0, 255).astype(np.uint8)
    colored = cv2.applyColorMap(img_u8, colormap)
    return colored.astype(np.float32)


def adjust_brightness_contrast(
    img_array: np.ndarray,
    brightness: float = 0.0,
    contrast: float = 1.0,
) -> np.ndarray:
    """
    Simple linear brightness/contrast adjustment:
      out = img * contrast + brightness

    brightness ∈ [-100..100], contrast ∈ [1..5] recommended.
    Works for 2D or 3D (color) arrays.
    """
    float_img = img_array.astype(np.float32)
    float_img = float_img * float(contrast) + float(brightness)
    return float_img


def apply_zoom_and_pan(
    img_array: np.ndarray,
    zoom_factor: float = 1.0,
    pan_x: float = 0.0,
    pan_y: float = 0.0,
) -> np.ndarray:
    """
    Zooms into the image around a center shifted by (pan_x, pan_y),
    then resizes back to the original resolution.
    - zoom_factor > 1.0: zoom in
    - zoom_factor < 1.0: zoom out (clamped to 0.5..10.0 in the viewer)
    - pan_x, pan_y: shifts of the zoom center in pixel space.

    img_array is expected to be either (H, W) or (H, W, C).
    """

    # If no zooming requested, return as-is
    if zoom_factor is None or abs(zoom_factor - 1.0) < 1e-6:
        return img_array

    if zoom_factor <= 0:
        zoom_factor = 1.0

    # Handle both grayscale (H, W) and color (H, W, C)
    if img_array.ndim == 2:
        h, w = img_array.shape
        channels = 1
    elif img_array.ndim == 3:
        h, w, channels = img_array.shape
    else:
        # Unsupported shape; just return original
        return img_array

    # Compute crop size
    crop_w = int(round(w / zoom_factor))
    crop_h = int(round(h / zoom_factor))

    # Ensure valid crop sizes
    crop_w = max(1, min(w, crop_w))
    crop_h = max(1, min(h, crop_h))

    # Compute zoom center in original image coords
    # Center starts from image center, then shifted by pan_x / pan_y
    cx = int(round(w / 2 + pan_x))
    cy = int(round(h / 2 + pan_y))

    # Clamp center so crop stays within bounds as much as possible
    half_w = crop_w // 2
    half_h = crop_h // 2

    x1 = cx - half_w
    y1 = cy - half_h
    x2 = x1 + crop_w
    y2 = y1 + crop_h

    # Adjust if out of bounds
    if x1 < 0:
        x1 = 0
        x2 = crop_w
    if y1 < 0:
        y1 = 0
        y2 = crop_h
    if x2 > w:
        x2 = w
        x1 = w - crop_w
    if y2 > h:
        y2 = h
        y1 = h - crop_h

    # Final safety clamp
    x1 = int(max(0, min(x1, w - 1)))
    y1 = int(max(0, min(y1, h - 1)))
    x2 = int(max(x1 + 1, min(x2, w)))
    y2 = int(max(y1 + 1, min(y2, h)))

    # Crop
    if img_array.ndim == 2:
        cropped = img_array[y1:y2, x1:x2]
    else:
        cropped = img_array[y1:y2, x1:x2, :]

    # Resize back to original size
    if channels == 1:
        cropped_u8 = np.clip(cropped, 0, 255).astype(np.uint8)
        resized = cv2.resize(cropped_u8, (w, h), interpolation=cv2.INTER_LINEAR)
        return resized.astype(np.float32)
    else:
        # Color image
        cropped_u8 = np.clip(cropped, 0, 255).astype(np.uint8)
        resized = cv2.resize(cropped_u8, (w, h), interpolation=cv2.INTER_LINEAR)
        return resized.astype(np.float32)

def apply_window_level(slice_raw: np.ndarray, center: float, width: float) -> np.ndarray:
    """
    Apply Window/Level mapping to a float32 slice in native units (e.g., HU).
    Returns float32 in [0, 255].
    """
    x = slice_raw.astype(np.float32, copy=False)
    x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)

    w = float(width)
    if w <= 1e-6:
        w = 1.0
    c = float(center)

    low = c - 0.5 - (w - 1.0) / 2.0
    high = c - 0.5 + (w - 1.0) / 2.0

    y = (x - low) / (high - low)
    y = np.clip(y, 0.0, 1.0) * 255.0
    return y.astype(np.float32)

def apply_all_processing(
    img_array: np.ndarray,
    hist_eq: bool = False,
    brightness_contrast: bool = False,
    brightness: float = 0.0,
    contrast: float = 1.0,
    colormap: bool = False,
    zoom_enabled: bool = False,
    zoom_factor: float = 1.0,
    pan_x: float = 0.0,
    pan_y: float = 0.0,
) -> np.ndarray:
    """
    Full processing pipeline:
      1. Histogram Equalization (optional, on grayscale)
      2. Brightness/Contrast (optional)
      3. Colormap (optional, converts grayscale to color)
      4. Zoom & Pan (optional)
    Returns a float32 array; viewer will clip to [0, 255] and convert to uint8.
    """

    # Make working copy as float32
    out = img_array.astype(np.float32)

    # 1) Histogram Equalization (only meaningful for single-channel)
    if hist_eq:
        if out.ndim == 2:
            out = apply_histogram_equalization(out)
        elif out.ndim == 3 and out.shape[2] == 1:
            out = apply_histogram_equalization(out[:, :, 0])
        else:
            # If already color, you might skip or convert to gray;
            # here we skip to avoid weird effects.
            pass

    # 2) Brightness / Contrast
    if brightness_contrast:
        out = adjust_brightness_contrast(
            out,
            brightness=float(brightness),
            contrast=float(contrast),
        )

    # 3) Colormap (only if image is single-channel)
    if colormap:
        if out.ndim == 2 or (out.ndim == 3 and out.shape[2] == 1):
            out = apply_colormap(out)
        # If already color, we skip applying another colormap

    # 4) Zoom & Pan
    if zoom_enabled:
        out = apply_zoom_and_pan(
            out,
            zoom_factor=float(zoom_factor),
            pan_x=float(pan_x),
            pan_y=float(pan_y),
        )

    return out.astype(np.float32)

def apply_zoom_and_pan_mask(
    mask_array: np.ndarray,
    zoom_factor: float = 1.0,
    pan_x: float = 0.0,
    pan_y: float = 0.0,
) -> np.ndarray:
    """
    Same geometry as apply_zoom_and_pan, but uses nearest-neighbor to preserve labels.
    mask_array must be 2D (H, W).
    Returns float32 or uint8 mask resized back to original (H, W).
    """
    if mask_array is None:
        return None

    if zoom_factor is None or abs(zoom_factor - 1.0) < 1e-6:
        return mask_array

    if zoom_factor <= 0:
        zoom_factor = 1.0

    m = mask_array
    if m.ndim != 2:
        m = np.squeeze(m)
        if m.ndim != 2:
            return mask_array

    h, w = m.shape

    crop_w = int(round(w / zoom_factor))
    crop_h = int(round(h / zoom_factor))
    crop_w = max(1, min(w, crop_w))
    crop_h = max(1, min(h, crop_h))

    cx = int(round(w / 2 + pan_x))
    cy = int(round(h / 2 + pan_y))

    half_w = crop_w // 2
    half_h = crop_h // 2

    x1 = cx - half_w
    y1 = cy - half_h
    x2 = x1 + crop_w
    y2 = y1 + crop_h

    if x1 < 0:
        x1 = 0
        x2 = crop_w
    if y1 < 0:
        y1 = 0
        y2 = crop_h
    if x2 > w:
        x2 = w
        x1 = w - crop_w
    if y2 > h:
        y2 = h
        y1 = h - crop_h

    x1 = int(max(0, min(x1, w - 1)))
    y1 = int(max(0, min(y1, h - 1)))
    x2 = int(max(x1 + 1, min(x2, w)))
    y2 = int(max(y1 + 1, min(y2, h)))

    cropped = m[y1:y2, x1:x2].astype(np.uint8)

    # Nearest-neighbor is critical for masks
    resized = cv2.resize(cropped, (w, h), interpolation=cv2.INTER_NEAREST)
    return resized
