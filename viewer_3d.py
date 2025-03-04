# viewer_3d.py
import vtk
from vtk.util import numpy_support
import image_loader
import numpy as np

def render_3d_image(file_path, modality):
    """ Create a 3D volume rendering of a DICOM or NIfTI file """
    file_type = image_loader.detect_file_type(file_path)

    if file_type == "DICOM":
        img_array = image_loader.load_dicom(file_path)
        # If it's truly a 3D DICOM (multiple slices), you might need a series loader
    elif file_type == "NIfTI":
        img_array = image_loader.load_nifti(file_path)
    else:
        print("Error: Only DICOM or NIfTI can be 3D rendered.")
        return

    # If 2D (e.g., single-slice) => can't do 3D. Check shape:
    if len(img_array.shape) < 3:
        # Expand dims artificially just to visualize or simply return an error
        print("Warning: The selected file is 2D, 3D rendering may not be meaningful.")
        img_array = np.expand_dims(img_array, axis=-1)

    vtk_data = numpy_support.numpy_to_vtk(num_array=img_array.ravel(), deep=True, array_type=vtk.VTK_FLOAT)

    image_data = vtk.vtkImageData()
    image_data.SetDimensions(img_array.shape)
    image_data.GetPointData().SetScalars(vtk_data)

    volume_mapper = vtk.vtkGPUVolumeRayCastMapper()
    volume_mapper.SetInputData(image_data)

    volume_property = vtk.vtkVolumeProperty()
    volume_property.ShadeOn()
    volume = vtk.vtkVolume()
    volume.SetMapper(volume_mapper)
    volume.SetProperty(volume_property)

    renderer = vtk.vtkRenderer()
    renderer.AddVolume(volume)

    render_window = vtk.vtkRenderWindow()
    render_window.SetWindowName(f"3D Viewer - {modality}")
    render_window.AddRenderer(renderer)

    render_interactor = vtk.vtkRenderWindowInteractor()
    render_interactor.SetRenderWindow(render_window)

    render_window.Render()
    render_interactor.Start()
