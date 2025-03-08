# viewer_3d.py
import vtk
from vtk.util import numpy_support
import image_loader
import numpy as np

def render_3d_image(file_path, modality):
    """ Create a 3D volume rendering of a DICOM or NIfTI file. """

    file_type = image_loader.detect_file_type(file_path)
    if file_type == "DICOM":
        # Single-file DICOM is typically 2D. For real 3D, you'd need multiple .dcm slices in a folder.
        img_array = image_loader.load_dicom(file_path)
        if len(img_array.shape) < 3:
            print("Warning: This is a single-slice DICOM, 3D rendering may not look meaningful.")
            # Expand dims just to show something in 3D:
            img_array = np.expand_dims(img_array, axis=-1)
    elif file_type == "NIfTI":
        # True 3D volume
        img_array = image_loader.load_nifti(file_path).astype(np.float32)
        if len(img_array.shape) < 3:
            print("Warning: NIfTI is actually 2D, 3D render might not be meaningful.")
            img_array = np.expand_dims(img_array, axis=-1)
    else:
        print("Error: Only DICOM or NIfTI can be 3D rendered.")
        return

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
