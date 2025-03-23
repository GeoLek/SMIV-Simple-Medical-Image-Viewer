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
    Zoom around the image center, then pan offsets the subregion.
      - zoom_factor > 1 => zoom in
      - pan_x, pan_y shift the subregion center
    """
    if zoom_factor == 1.0:
        return img_array

    h, w = img_array.shape[:2]
    # The subregion size is (w/zoom_factor, h/zoom_factor).
    crop_w = int(w / zoom_factor)
    crop_h = int(h / zoom_factor)

    # The base center is (w/2, h/2). We add (pan_x, pan_y) to it.
    center_x = w * 0.5 + pan_x
    center_y = h * 0.5 + pan_y

    # Now we compute x1,y1 from the center minus half the cropped size
    x1 = center_x - crop_w * 0.5
    y1 = center_y - crop_h * 0.5
    x2 = x1 + crop_w
    y2 = y1 + crop_h

    # Convert to int for slicing
    x1, y1, x2, y2 = map(int, [x1, y1, x2, y2])

    # Bound checks
    if x1 < 0: x1 = 0
    if y1 < 0: y1 = 0
    if x2 > w: x2 = w
    if y2 > h: y2 = h

    if x2 <= x1 or y2 <= y1:
        # invalid subregion => return original
        return img_array

    cropped = img_array[y1:y2, x1:x2].astype(np.uint8)
    # We scale back to the original size, so the final displayed image is always (h,w).
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
    # Use these for pan offsets
    pan_x=0.0,
    pan_y=0.0,
    # If you prefer "zoom_center_x" and "zoom_center_y" logic, remove pan entirely
):
    out = img_array.copy()

    # 1) Hist eq
    if hist_eq:
        out = apply_histogram_equalization(out)

    # 2) Brightness/Contrast
    if brightness_contrast:
        out = adjust_brightness_contrast(out, brightness=brightness, contrast=contrast)

    # 3) Colormap
    if colormap:
        out = apply_colormap(out)

    # 4) Zoom + Pan
    if zoom_enabled and zoom_factor != 1.0:
        out = apply_zoom_and_pan(out, zoom_factor=zoom_factor, pan_x=pan_x, pan_y=pan_y)

    return out
