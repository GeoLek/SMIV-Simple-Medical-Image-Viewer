# SMIV: Simple Medical Image Viewer

SMIV is a lightweight, cross-platform medical image viewer supporting:
- **DICOM** (with or without `.dcm` extension),
- **NIfTI** (`.nii`, `.nii.gz`),
- **PNG/JPG** for 2D images,
- **Multi-slice/time** navigation (3D/4D volumes),
- **Preprocessing** (histogram equalization, brightness/contrast, colormap),
- **Zoom** (mouse-wheel) and **Pan** (left-drag),
- **Multi-file scanning** in a single directory,
- **Automatic detection** of file formats (even if they have no extension).

It's written in Python using **Tkinter** (for the GUI) and **PIL/numpy/opencv** (for image processing).


## Features

1. **DICOM** reading with or without `.dcm` extension (using pydicom).
2. **NIfTI** reading for 3D/4D volumes (via nibabel).
3. **PNG/JPG** single-slice images.
4. **Preprocessing Tools**:
   - Histogram Equalization
   - Brightness/Contrast
   - Colormap (JET)
   - Zoom & Pan  
5. **Metadata Window** for each file, displaying basic DICOM tags or NIfTI headers.
6. **Navigation**:
   - Sliders for multiple files in the same directory,
   - Sliders for slices/time dimension if it’s a 3D/4D dataset,
   - “Prev/Next” file buttons,
   - A file index slider for quick scanning.


## System Requirements

- **Python 3.7+** (3.9+ recommended).
- **pip** or **conda** to install dependencies.
- One of the following operating systems:
  - **Linux (Debian/Ubuntu)** with `python3-tk` installed.
  - **Windows** with standard Python installation (includes Tkinter).
  - **macOS** with standard Python (3.9+).
- Libraries needed:
  - `pydicom` (DICOM)
  - `nibabel` (NIfTI)
  - `numpy`
  - `Pillow` (PNG/JPG)
  - `opencv-python` (colormap & resizing)
  - `tkinter` (should be included, but on Linux you might need `sudo apt-get install python3-tk`).

## Installation

### A) Quick Setup with pip

1. **Clone or Download** the repository:
   
   git clone https://github.com/GeoLek/SMIV-Simple-Medical-Image-Viewer  
   cd SMIV-Simple-Medical-Image-Viewer

2. Create a Virtual Environment (recommended):
   
   python -m venv venv
   source venv/bin/activate     # On Windows: venv\Scripts\activate

3. Install Required Libraries:
   
   pip install -r requirements.txt

4. Run the program:
   
   python main.py

## Building an Executable

### PyInstaller (Cross-Platform)

If you'd like a single-file `.exe` (Windows) or `.app` (macOS) or an ELF on Linux:

1. **Install** PyInstaller:
   pip install pyinstaller
2. Run:
pyinstaller --onefile main.py
4. The dist/ folder will contain main.exe (on Windows) or just main on Linux, etc.
5. Double-click or run it from the terminal; it launches the SMIV GUI.

   
