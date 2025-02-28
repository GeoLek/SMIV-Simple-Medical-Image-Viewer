import cv2
import numpy as np

def apply_histogram_equalization(img_array, enabled=True):
    """ Enhance image contrast using histogram equalization (optional) """
    if not enabled:
        return img_array
    img_array = img_array.astype(np.uint8)
    return cv2.equalizeHist(img_array)

def apply_colormap(img_array, enabled=True, colormap=cv2.COLORMAP_JET):
    """ Apply a pseudocolor colormap to grayscale image (optional) """
    if not enabled:
        return img_array
    img_array = img_array.astype(np.uint8)
    return cv2.applyColorMap(img_array, colormap)

def adjust_brightness_contrast(img_array, brightness=0, contrast=1.0, enabled=True):
    """ Adjust image brightness and contrast (optional) """
    if not enabled:
        return img_array
    img_array = img_array.astype(np.float32) * contrast + brightness
    img_array = np.clip(img_array, 0, 255)
    return img_array.astype(np.uint8)

def apply_zoom(img_array, zoom_factor=1.0, enabled=True):
    """ Zoom in or out on the image (optional) """
    if not enabled or zoom_factor == 1.0:
        return img_array

    height, width = img_array.shape[:2]
    new_width, new_height = int(width * zoom_factor), int(height * zoom_factor)

    center_x, center_y = width // 2, height // 2
    x1, y1 = max(center_x - new_width // 2, 0), max(center_y - new_height // 2, 0)
    x2, y2 = min(center_x + new_width // 2, width), min(center_y + new_height // 2, height)

    zoomed_img = img_array[y1:y2, x1:x2]
    return cv2.resize(zoomed_img, (width, height), interpolation=cv2.INTER_LINEAR)
