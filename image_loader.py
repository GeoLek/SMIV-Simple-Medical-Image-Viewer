import pydicom
import nibabel as nib
import numpy as np

def load_dicom(file_path):
    """ Load DICOM image and return normalized NumPy array """
    dicom_data = pydicom.dcmread(file_path)
    img_array = dicom_data.pixel_array.astype(np.float32)
    img_array = (img_array - img_array.min()) / (img_array.max() - img_array.min()) * 255
    return img_array

def load_nifti(file_path):
    """ Load NIfTI image and return middle slice as NumPy array """
    nii_data = nib.load(file_path)
    img_array = nii_data.get_fdata()
    mid_slice = img_array[:, :, img_array.shape[2] // 2]
    mid_slice = (mid_slice - mid_slice.min()) / (mid_slice.max() - mid_slice.min()) * 255
    return mid_slice
