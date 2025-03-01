import tkinter as tk
from tkinter import filedialog
import viewer_2d
import viewer_3d

def run_2d_viewer():
    viewer_2d.create_2d_viewer()

def run_3d_viewer():
    file_path = filedialog.askopenfilename(filetypes=[("DICOM Series", "*.dcm"), ("NIfTI Files", "*.nii;*.nii.gz")])
    if file_path:
        viewer_3d.render_3d_image(file_path)

# Tkinter Main Window
root = tk.Tk()
root.title("Medical Image Viewer")

btn_2d = tk.Button(root, text="Open 2D Viewer", command=run_2d_viewer)
btn_2d.pack()

btn_3d = tk.Button(root, text="Open 3D Viewer", command=run_3d_viewer)
btn_3d.pack()

root.mainloop()
