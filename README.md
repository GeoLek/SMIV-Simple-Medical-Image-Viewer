# SMIV: Simple Medical Image Viewer

SMIV is a lightweight, cross-platform medical image viewer supporting:
- **DICOM** (with or without `.dcm` extension),
- **NIfTI** (`.nii`, `.nii.gz`),
- **PNG/JPG** for 2D images,
- **TIFF/Whole‐Slide Imaging (WSI)** for `.svs/.tiff/.ndpi/.scn` (using OpenSlide),
- **Multi-slice/time** navigation (3D/4D volumes),
- **Preprocessing** (histogram equalization, brightness/contrast, colormap),
- **Zoom** (mouse-wheel) and **Pan** (left-drag),
- **Multi-file scanning** in a single directory,
- **Automatic detection** of file formats (even if they have no extension).

It's written in Python using **Tkinter** for the GUI, **Pillow/numpy/opencv** for image processing, and **OpenSlide** (optional) to handle `.svs` and other large pathology slides.

---

## Features

1. **DICOM** reading with or without `.dcm` (using `pydicom`).
2. **NIfTI** reading for 3D/4D volumes (via `nibabel`).
3. **PNG/JPG** single-slice images.
4. **TIFF/WSI** support:
   - Single/multi-page `.tif` with Pillow
   - Whole-slide `.svs`, `.scn`, `.mrxs`, `.ndpi` with OpenSlide
5. **Preprocessing Tools**:
   - Histogram Equalization
   - Brightness/Contrast
   - Colormap (JET)
   - Zoom & Pan
6. **Metadata Window** for each file, displaying basic DICOM tags or NIfTI/OpenSlide headers.
7. **Navigation**:
   - Sliders for multiple files in the same directory
   - Sliders for slices/time dimension if it’s a 3D/4D dataset
   - “Prev/Next” file buttons
   - File index slider for quick scanning

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

## TIFF/WSI Support

- **Single-page TIFF** files are handled by **Pillow**.
- **Whole-slide** files (like `.svs`, `.scn`, `.mrxs`, `.ndpi`) require **OpenSlide**.
- SMIV automatically detects large WSI files and loads a downsampled level or bounding region to display the entire tissue. This prevents memory overload and avoids blank images.
- You can still apply brightness/contrast, histogram equalization, colormap, zoom, and pan to the downsampled slide.

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

   
