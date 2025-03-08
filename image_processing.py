# image_processing.py
import cv2
import numpy as np


def apply_histogram_equalization(img_array, enabled=True):
    if not enabled:
        return img_array
    img_array = img_array.astype(np.uint8)
    return cv2.equalizeHist(img_array)


def apply_colormap(img_array, enabled=True, colormap=cv2.COLORMAP_JET):
    if not enabled:
        return img_array
    img_array = img_array.astype(np.uint8)
    return cv2.applyColorMap(img_array, colormap)


def adjust_brightness_contrast(img_array, brightness=0.0, contrast=1.0, enabled=True):
    if not enabled:
        return img_array
    # brightness in range [-100, +100], contrast in [1..5]
    float_img = img_array.astype(np.float32)
    float_img = float_img * contrast + brightness
    return float_img


def apply_zoom(img_array, zoom_factor=1.0, enabled=True):
    """
    Zoom logic:
      - If zoom_factor == 1.0 or disabled => no change
      - If zoom_factor > 1.0 => 'zoom in'
        => take smaller center crop, then scale up to original shape
      - If zoom_factor < 1.0 => 'zoom out' (not typical for medical, but supported)
        => take bigger area (?), but we only have the original image...
    """
    if not enabled or zoom_factor == 1.0:
        return img_array

    height, width = img_array.shape[:2]

    # We'll do 'zoom in' if zoom_factor > 1 => crop out a smaller region
    # Then scale that smaller region back to the original size.
    if zoom_factor > 1.0:
        crop_width = int(width / zoom_factor)
        crop_height = int(height / zoom_factor)
    else:
        # zoom out logic => bigger region than the entire image?
        # Not possible, so let's interpret zoom < 1 as ignoring or just partial
        crop_width = int(width * zoom_factor)
        crop_height = int(height * zoom_factor)

    if crop_width < 1 or crop_height < 1:
        return img_array  # can't crop if it's too small

    center_x, center_y = width // 2, height // 2
    x1 = max(center_x - crop_width // 2, 0)
    y1 = max(center_y - crop_height // 2, 0)
    x2 = min(x1 + crop_width, width)
    y2 = min(y1 + crop_height, height)

    cropped = img_array[y1:y2, x1:x2]

    # Now scale that region back to the original size
    zoomed_img = cv2.resize(cropped, (width, height), interpolation=cv2.INTER_LINEAR)
    return zoomed_img
