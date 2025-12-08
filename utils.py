# utils.py

from PIL import Image

def save_as_png(img_array, output_path):
    """ Save NumPy array as PNG image """
    img = Image.fromarray(img_array.astype("uint8"))
    img.save(output_path, format="PNG")
