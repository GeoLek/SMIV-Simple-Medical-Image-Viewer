# image_processing.py

import numpy as np
import cv2

def apply_histogram_equalization(img_array):
    img_array = img_array.astype(np.uint8)
    return cv2.equalizeHist(img_array)

def apply_colormap(img_array, colormap=cv2.COLORMAP_JET):
    img_array = img_array.astype(np.uint8)
    return cv2.applyColorMap(img_array, colormap)

def adjust_brightness_contrast(img_array, brightness=0.0, contrast=1.0):
    float_img = img_array.astype(np.float32)
    float_img = float_img * contrast + brightness
    return float_img

def apply_zoom_and_pan(img_array, zoom_factor=1.0, pan_x=0.0, pan_y=0.0):
    """
    Zoom in/out around the image center, then shift the subregion by pan_x/pan_y.
    We'll interpret pan_x, pan_y as offsets in pixel coords.
    """
    if zoom_factor == 1.0 and (pan_x == 0.0 and pan_y == 0.0):
        return img_array

    h, w = img_array.shape[:2]

    crop_w = int(w / zoom_factor)
    crop_h = int(h / zoom_factor)

    # The base center is (w/2, h/2). Shift by pan_x, pan_y.
    center_x = w * 0.5 + pan_x
    center_y = h * 0.5 + pan_y

    x1 = center_x - crop_w * 0.5
    y1 = center_y - crop_h * 0.5
    x2 = x1 + crop_w
    y2 = y1 + crop_h

    # Cast to int
    x1, y1, x2, y2 = map(int, [x1, y1, x2, y2])

    # Bound checks
    if x1 < 0: x1 = 0
    if y1 < 0: y1 = 0
    if x2 > w: x2 = w
    if y2 > h: y2 = h

    if x2 <= x1 or y2 <= y1:
        return img_array

    cropped = img_array[y1:y2, x1:x2].astype(np.uint8)
    resized = cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)
    return resized.astype(np.float32)

def apply_all_processing(
    img_array,
    hist_eq=False,
    brightness_contrast=False,
    brightness=0.0,
    contrast=1.0,
    colormap=False,
    zoom_enabled=False,
    zoom_factor=1.0,
    pan_x=0.0,
    pan_y=0.0
):
    out = img_array.copy()

    # 1) hist eq
    if hist_eq:
        out = apply_histogram_equalization(out)

    # 2) brightness/contrast
    if brightness_contrast:
        out = adjust_brightness_contrast(out, brightness=brightness, contrast=contrast)

    # 3) colormap
    if colormap:
        out = apply_colormap(out)

    # 4) zoom + pan
    if zoom_enabled:
        out = apply_zoom_and_pan(out, zoom_factor=zoom_factor, pan_x=pan_x, pan_y=pan_y)

    return out
