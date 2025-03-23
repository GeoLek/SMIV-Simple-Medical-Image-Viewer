# viewer_multi_logic.py

import os
import nibabel as nib
import numpy as np
import image_loader
import image_processing

class MultiSliceTimeLogic:
    """
    This class encapsulates all the logic for:
      1) Multi-file navigation
      2) Multi-slice/time 3D/4D volumes
      3) Preprocessing (hist eq, brightness/contrast, colormap, zoom)
      4) Storing state for the image
      5) Loading metadata
      6) Displaying slices
    """

    def __init__(self, file_paths):
        # Minimal shared state
        self.file_paths = file_paths
        self.current_file_index = 0
        self.volume = None  # 4D => shape (H, W, Z, T)
        self.z_index = 0
        self.t_index = 0
        self.z_max = 1
        self.t_max = 1
        self.zoom_factor = 1.0
        self.zoom_enabled = False
        self.cursor_x = 0
        self.cursor_y = 0

    # --------------
    # File Navigation
    # --------------
    def change_file(self, delta):
        new_idx = (self.current_file_index + delta) % len(self.file_paths)
        self.current_file_index = new_idx
        return new_idx  # So the UI can update file_slider etc.

    def set_file_index(self, idx):
        self.current_file_index = idx

    def get_file_index(self):
        return self.current_file_index

    # --------------
    # Load & Metadata
    # --------------
    def load_current_file(self):
        """
        Loads the current file into self.volume, determines shape,
        returns (file_type, metadata_str) for the UI to show
        """
        path = self.file_paths[self.current_file_index]
        file_type, meta_str = image_loader.detect_file_type_and_metadata(path)

        # Load volume
        if file_type == "DICOM":
            arr = image_loader.load_dicom(path)
            if arr.ndim == 2:
                arr = arr[..., np.newaxis, np.newaxis]
            elif arr.ndim == 3:
                arr = arr[..., np.newaxis]
            self.volume = arr
        elif file_type == "NIfTI":
            vol = nib.load(path).get_fdata()
            if vol.ndim == 2:
                vol = vol[..., np.newaxis, np.newaxis]
            elif vol.ndim == 3:
                vol = vol[..., np.newaxis]
            self.volume = vol
        elif file_type == "JPEG/PNG":
            arr = image_loader.load_jpeg_png(path)
            arr = arr[..., np.newaxis, np.newaxis]
            self.volume = arr
        else:
            self.volume = None

        # Setup shape
        if self.volume is not None:
            shape_4d = self.volume.shape  # => (H, W, Z, T)
            self.z_max = shape_4d[2]
            self.t_max = shape_4d[3]
            # Reset slices
            self.z_index = min(self.z_max // 2, self.z_max - 1)
            self.t_index = min(self.t_max // 2, self.t_max - 1)
        else:
            self.z_max = 1
            self.t_max = 1

        return file_type, meta_str

    # --------------
    # Slice/Time Navigation
    # --------------
    def set_z_index(self, z):
        self.z_index = z

    def set_t_index(self, t):
        self.t_index = t

    def get_z_max(self):
        return self.z_max

    def get_t_max(self):
        return self.t_max

    # --------------
    # Zoom & Cursor
    # --------------
    def toggle_zoom(self, enabled):
        self.zoom_enabled = enabled

    def on_wheel_zoom(self, direction):
        if not self.zoom_enabled:
            return
        factor = 1.1
        if direction > 0:
            self.zoom_factor *= factor
        else:
            self.zoom_factor /= factor
        self.zoom_factor = max(0.5, min(10.0, self.zoom_factor))

    def set_cursor_pos(self, x, y):
        self.cursor_x = x
        self.cursor_y = y

    # --------------
    # Preprocessing Display
    # --------------
    def get_slice_for_display(self,
                              hist_eq=False,
                              brightness_contrast=False,
                              brightness=0,
                              contrast=1,
                              colormap=False):
        """
        Returns a 2D NumPy array (uint8) of the currently selected slice,
        with all preprocessing (zoom, etc.) applied.
        If volume is None, returns None.
        """
        if self.volume is None:
            return None

        slice_2d = self.volume[..., self.z_index, self.t_index]
        # Normalize to [0..255]
        min_val, max_val = slice_2d.min(), slice_2d.max()
        if max_val != min_val:
            slice_2d = (slice_2d - min_val) / (max_val - min_val) * 255
        slice_2d = slice_2d.astype(np.float32)

        # Apply processing
        out = image_processing.apply_all_processing(
            slice_2d,
            hist_eq=hist_eq,
            brightness_contrast=brightness_contrast,
            brightness=brightness,
            contrast=contrast,
            colormap=colormap,
            zoom_enabled=self.zoom_enabled,
            zoom_factor=self.zoom_factor,
            zoom_center_x=self.cursor_x,
            zoom_center_y=self.cursor_y
        )
        out = np.clip(out, 0, 255).astype(np.uint8)
        return out
