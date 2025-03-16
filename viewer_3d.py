import tkinter as tk
from tkinter import ttk, BooleanVar, IntVar, Checkbutton, Scale
import numpy as np
import nibabel as nib
import pydicom
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import image_loader
import image_processing


class MedicalImageViewer3D:
    def __init__(self, root, file_path):
        self.root = root
        self.file_path = file_path
        self.file_type, self.metadata = image_loader.detect_file_type_and_metadata(file_path)

        # Load Image Data
        self.load_image_data()

        # Initialize UI
        self.create_ui()

    def load_image_data(self):
        """ Load DICOM or NIfTI Image """
        if self.file_type == "DICOM":
            self.image_data = image_loader.load_dicom(self.file_path)
        elif self.file_type == "NIfTI":
            self.image_data = image_loader.load_nifti(self.file_path)
        else:
            print("Unsupported format.")
            self.root.destroy()
            return

        # Ensure at least 3D shape
        while self.image_data.ndim < 3:
            self.image_data = np.expand_dims(self.image_data, axis=-1)

        self.current_slice = self.image_data.shape[-1] // 2  # Start at middle slice
        self.zoom_factor = 1.0
        self.zoom_enabled = False  # ✅ FIXED: Use a proper instance variable

        self.settings = {
            "hist_eq": BooleanVar(value=False),
            "colormap": BooleanVar(value=False),
            "brightness_contrast": BooleanVar(value=False),
            "brightness": IntVar(value=0),
            "contrast": IntVar(value=1),
        }

    def create_ui(self):
        """ Create UI with image display and navigation """
        self.root.title("3D Medical Image Viewer")

        # Display Image Slice
        self.figure, self.ax = plt.subplots()
        self.canvas = FigureCanvasTkAgg(self.figure, self.root)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Slice Navigation
        self.slider = ttk.Scale(self.root, from_=0, to=self.image_data.shape[-1] - 1,
                                orient="horizontal", command=self.update_slice)
        self.slider.set(self.current_slice)
        self.slider.pack(fill=tk.X, padx=10, pady=5)

        # Metadata Window
        self.metadata_window = tk.Toplevel(self.root)
        self.metadata_window.title("Image Metadata")
        tk.Label(self.metadata_window, text=self.metadata, justify=tk.LEFT).pack(padx=10, pady=10)

        # Preprocessing Controls (Vertical Layout)
        controls_frame = tk.Frame(self.root)
        controls_frame.pack(side=tk.TOP, fill=tk.X)

        # Histogram Equalization
        Checkbutton(controls_frame, text="Histogram Equalization", variable=self.settings["hist_eq"],
                    command=self.update_image).pack(side=tk.TOP, anchor="w")

        # Colormap
        Checkbutton(controls_frame, text="Apply Colormap", variable=self.settings["colormap"],
                    command=self.update_image).pack(side=tk.TOP, anchor="w")

        # Brightness/Contrast
        Checkbutton(controls_frame, text="Brightness/Contrast", variable=self.settings["brightness_contrast"],
                    command=self.update_image).pack(side=tk.TOP, anchor="w")

        # Sliders for Brightness & Contrast
        Scale(controls_frame, from_=-100, to=100, label="Brightness",
              variable=self.settings["brightness"], orient=tk.HORIZONTAL,
              command=lambda v: self.update_image()).pack(side=tk.TOP, fill=tk.X)

        Scale(controls_frame, from_=1, to=5, resolution=0.1, label="Contrast",
              variable=self.settings["contrast"], orient=tk.HORIZONTAL,
              command=lambda v: self.update_image()).pack(side=tk.TOP, fill=tk.X)

        # ✅ FIXED: Now zoom is a proper instance variable
        self.zoom_enabled_var = BooleanVar(value=False)
        Checkbutton(controls_frame, text="Enable Mouse Zoom", variable=self.zoom_enabled_var,
                    command=self.toggle_zoom).pack(side=tk.TOP, anchor="w")

        # ✅ Bind Mouse Wheel for Zoom
        self.root.bind("<MouseWheel>", self.on_mouse_wheel)

        # Render Initial Slice
        self.display_slice()

    def display_slice(self):
        """ Display the selected slice with preprocessing """
        img_array = self.image_data[:, :, self.current_slice]

        # Apply Processing
        img_array = image_processing.apply_all_processing(
            img_array,
            hist_eq=self.settings["hist_eq"].get(),
            brightness_contrast=self.settings["brightness_contrast"].get(),
            brightness=self.settings["brightness"].get(),
            contrast=self.settings["contrast"].get(),
            colormap=self.settings["colormap"].get(),
            zoom_enabled=self.zoom_enabled,  # ✅ FIXED
            zoom_factor=self.zoom_factor
        )

        self.ax.clear()
        self.ax.imshow(img_array, cmap="gray", aspect="auto")
        self.ax.set_title(f"Slice {self.current_slice + 1}/{self.image_data.shape[-1]}")
        self.ax.axis("off")

        self.canvas.draw()

    def update_slice(self, value):
        """ Update displayed slice when slider moves """
        self.current_slice = int(float(value))
        self.display_slice()

    def toggle_zoom(self):
        """ Enable or disable zoom mode """
        self.zoom_enabled = self.zoom_enabled_var.get()
        self.update_image()

    def on_mouse_wheel(self, event):
        """ Handle mouse wheel zoom """
        if not self.zoom_enabled:
            return
        step = 1.1
        if event.delta > 0:
            self.zoom_factor *= step
        else:
            self.zoom_factor /= step
        self.zoom_factor = max(0.5, min(10.0, self.zoom_factor))
        self.display_slice()


def create_3d_viewer(file_path):
    """ Launches the Medical Image Viewer """
    root = tk.Toplevel()
    MedicalImageViewer3D(root, file_path)
    root.mainloop()
