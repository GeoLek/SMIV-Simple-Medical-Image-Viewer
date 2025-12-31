# SMIV: Simple Medical Image Viewer

SMIV is a lightweight, cross-platform medical image viewer designed for quickly browsing heterogeneous medical imaging studies and research datasets. It supports:

- **DICOM** (with or without `.dcm` extension), including **series stacking when possible** with **single-file fallback**,
- **NIfTI** (`.nii`, `.nii.gz`) including 3D/4D volumes, with optional **reorientation to canonical (RAS)** and **multi-plane viewing** (**Axial/Coronal/Sagittal**),
- **PNG/JPG** for 2D images,
- **TIFF** for standard 2D images,
- **Whole-Slide Imaging (WSI)** formats like `.svs/.ndpi/.scn/.mrxs` (via **OpenSlide**, optional),
- **Multi-file directory scanning** (browse all recognized images in the same folder),
- **Automatic format detection** (even when files have no extension),
- **Multi-slice/time navigation** for 3D/4D datasets,
- **Preprocessing controls** (histogram equalization, brightness/contrast, colormap), plus **Window/Level (WL)** controls for grayscale volumes,
- **Interactive viewing** with **Zoom** (mouse wheel) and **Pan** (left-drag),
- **Segmentation overlay support** (binary + multi-class), including:
  - **Load/Clear mask** (NIfTI / PNG / TIFF / NPY),
  - **Per-label color mapping** (auto-generated),
  - **Per-label visibility toggles** (show/hide selected labels),
  - **Label filtering/search** (quickly find labels by id/name),
  - **Label names support** (auto-load sidecar JSON or manual label-map JSON),
  - **Mask/image mismatch warning** (warn once per loaded mask),
  - **Outline-only overlay mode** (optional),
- **Pixel Inspector** (hover to read pixel intensity/RGB and, if present, mask label + label name),
- **Export Current View** (save the displayed view as PNG),
- **Session Presets (per-file)**: save and restore preprocessing + overlay settings automatically,
- **Improved UI layout**: split view with a **resizable PanedWindow** (image on the left, toolbox on the right),
- **Toolbox tabs** for clarity: **Navigation**, **Preprocessing**, **Overlay**,
- **Quick Actions bar** at the **bottom-right** for safe, frequent actions (with confirmation prompts).

SMIV is written in Python using **Tkinter** for the GUI, **Pillow / NumPy / OpenCV** for image handling and overlays, **NiBabel** for NIfTI, **pydicom** for DICOM, and **OpenSlide** (optional) for WSI.

---

## Features

1. **DICOM** reading with or without `.dcm` (using `pydicom`), including **series stacking (when available)** with **fallback to single-file loading**.
2. **NIfTI** reading for 3D/4D volumes (via `nibabel`), including:
   - optional **reorientation to canonical (RAS)** (toggle, default ON),
   - **Axial/Coronal/Sagittal plane viewing** (NIfTI only).
3. **PNG/JPG** support for 2D images (grayscale or RGB).
4. **TIFF / WSI** support:
   - Standard `.tif/.tiff` images using Pillow
   - Whole-slide formats (`.svs/.ndpi/.scn/.mrxs`) via OpenSlide (if installed)
5. **Preprocessing Tools**:
   - Histogram Equalization
   - Brightness/Contrast
   - Colormap (JET)
   - **Window/Level (WL)** for grayscale volumes
     - CT presets (Soft tissue / Lung / Bone) when CT is detected
     - Auto WL (robust percentile-based)
   - Reset preprocessing to defaults
6. **Segmentation Overlays (binary + multi-class)**:
   - Load/Clear mask (NIfTI/PNG/TIFF/NPY)
   - Per-label colormap (auto)
   - Per-label visibility toggles (checkboxes)
   - **Label search/filter** + quick actions (**All / None / Invert**)
   - Label names via:
     - sidecar JSON auto-detection (safe optional)
     - manual “label-map JSON” file loading
   - Outline-only mode
   - One-time mismatch warning if mask and image geometry differ
7. **Metadata Window** for each file (DICOM tags, NIfTI header, OpenSlide info).
8. **Navigation**:
   - “Prev/Next” file buttons + file slider
   - Slice (Z) and time (T) sliders for 3D/4D datasets
   - **Plane-aware Z navigation** for NIfTI (Z adapts to Axial/Coronal/Sagittal)
   - Keyboard shortcuts for fast browsing (file / Z / T)
   - **Export Current View as PNG**
9. **UX Improvements**:
   - Split-pane layout (image left, toolbox right)
   - Bottom-right Quick Actions with confirmations for destructive resets
   - Pixel Inspector (hover readout in the status bar)
   - **Session Presets (per-file)**: Save/Apply presets for preprocessing + overlay settings

---

## System Requirements

- **Python 3.7+** (3.9+ recommended).
- **pip** or **conda** to install dependencies.
- Operating systems:
  - **Linux (Debian/Ubuntu)** with `python3-tk` installed.
  - **Windows** with standard Python (includes Tkinter).
  - **macOS** with standard Python (3.9+).
- Required libraries:
  - `pydicom` (DICOM)
  - `nibabel` (NIfTI)
  - `numpy`
  - `Pillow` (PNG/JPG, plus some TIFF)
  - `opencv-python` (colormap/resizing - optional but recommended)
  - `tkinter` (usually included; on Linux, `sudo apt-get install python3-tk`)
  - **OpenSlide** (only if you need `.svs`/WSI support):
    - **Linux**:
      ```
      sudo apt-get install libopenslide-dev
      pip install openslide-python
      ```
    - **Windows**:
      - Either install from [OpenSlide Windows binaries](https://openslide.org/download/)
        or use Conda:
        ```
        conda install -c conda-forge openslide
        pip install openslide-python
        ```
    - **macOS**:
      ```
      brew install openslide
      pip install openslide-python
      ```

---

## Installation

### A) Quick Setup with pip

1. **Clone or Download** the repository:
   
   git clone https://github.com/GeoLek/SMIV-Simple-Medical-Image-Viewer  
   cd SMIV-Simple-Medical-Image-Viewer

2. **Create a Virtual Environment** (recommended):
   
   python -m venv venv
   source venv/bin/activate

   (On Windows: venv\Scripts\activate)

3. **Install Required Libraries**:
   
   pip install -r requirements.txt
   (Install `openslide-python` & system libs if `.svs` support is needed.)

4. **Run the program**:
   
   python main.py

---

## Building an Executable

### PyInstaller (Cross-Platform)

If you'd like a single-file `.exe` (Windows), `.app` (macOS), or a standalone on Linux:

1. **Install** PyInstaller:
   pip install pyinstaller
2. **Build**:
pyinstaller --onefile main.py
3. The `dist/` folder will contain `main.exe` (Windows) or `main` (Linux), etc.
4. Double-click or run it from the terminal; it launches the SMIV GUI.

---

   
