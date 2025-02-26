import tkinter as tk
from tkinter import filedialog
import pydicom
import nibabel as nib
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image, ImageTk
import os


def open_file():
    file_path = filedialog.askopenfilename(filetypes=[("DICOM files", "*.dcm"), ("NIfTI files", "*.nii;*.nii.gz")])
    if file_path:
        load_image(file_path)


def load_image(file_path):
    global img_label

    ext = os.path.splitext(file_path)[-1].lower()
    if ext == ".dcm":
        dicom_data = pydicom.dcmread(file_path)
        img_array = dicom_data.pixel_array
    elif ext in [".nii", ".nii.gz"]:
        nii_data = nib.load(file_path)
        img_array = np.rot90(nii_data.get_fdata()[:, :, nii_data.shape[2] // 2])  # Show middle slice
    else:
        return

    img_array = (img_array - img_array.min()) / (img_array.max() - img_array.min()) * 255  # Normalize
    img_pil = Image.fromarray(img_array.astype(np.uint8))
    img_tk = ImageTk.PhotoImage(img_pil)

    img_label.config(image=img_tk)
    img_label.image = img_tk


def convert_to_png():
    if img_label.image:
        file_path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG files", "*.png")])
        if file_path:
            img_label.image.write(file_path, format="png")


# Tkinter GUI setup
root = tk.Tk()
root.title("Medical Image Viewer")
root.geometry("600x600")

btn_open = tk.Button(root, text="Open File", command=open_file)
btn_open.pack()

btn_save = tk.Button(root, text="Save as PNG", command=convert_to_png)
btn_save.pack()

img_label = tk.Label(root)
img_label.pack()

root.mainloop()
