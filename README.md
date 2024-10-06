# Keypoint Annotation Tool

## Overview

The **Keypoint Annotation Tool** is a powerful and flexible desktop application designed for annotating keypoints on images, particularly useful for creating skeleton-based annotations. Built with **PyQt5** and **OpenCV**, this tool supports both **LMG** and **Rifle** skeleton structures, but it can be easily adapted for other object types. It features a user-friendly interface with advanced functionalities like zooming, panning, undo/redo, and image dataset management, making it suitable for computer vision projects involving pose estimation and object detection.

In addition to the source code, an executable file (`exe`) is available in the repository, so users can run the tool without setting up a Python environment.

## Key Features

- **Multi-Skeleton Annotation**: Annotate images using predefined skeletons for different object types (e.g., LMG, Rifle).
- **Customizable Keypoint Positions**: Easily adjust keypoint locations with mouse clicks and drags.
- **Zoom & Pan Support**: Zoom into images and pan across them for more detailed annotations.
- **Undo/Redo Functionality**: Quickly undo or redo any changes to annotations.
- **Image Dataset Navigation**: Seamlessly navigate through your dataset with 'Next' and 'Previous' buttons or keyboard shortcuts.
- **Real-Time & Manual Annotation Saving**: Automatically save annotations or save them manually to YOLO format files.
- **Cache for Temporary Annotations**: Annotations are temporarily stored in memory, ensuring you don't lose any unsaved data while navigating images.
- **Frame Extraction**: Extract frames from video files and save them as images for annotation.
- **Batch Image Resizing**: Resize entire image folders while maintaining aspect ratios, if desired.
- **Executable File**: No need to install dependencies! You can download and run the `.exe` file directly from the repository.

## Screenshots

Here are some screenshots of the Keypoint Annotation Tool in action:

### Main Interface

![Main Interface](./Interface%20Images//Main%20Interface.png)

*The main interface showing an image being annotated with keypoints and skeleton structure.*

### LMG Skeleton Annotation

![LMG Skeleton Annotation](./Interface%20Images//LMG%20Skeleton%20Annotation.png)

*Annotating an image using the LMG skeleton.*

### Rifle Skeleton Annotation

![Rifle Skeleton Annotation](./Interface%20Images//Rifle%20Skeleton%20Annotation.png)

*Annotating an image using the Rifle skeleton.*

### Frame Extraction Tool

![Frame Extraction Tool](./Interface%20Images//Frame%20Extraction%20Tool.png)

*The frame extraction dialog for extracting frames from video files.*

### Image Resizing Tool

![Image Resizing Tool](./Interface%20Images//Image%20Resizing%20Tool.png)

*The image resizing dialog for batch resizing images.*

## Supported Image Formats

`.png`, `.jpg`, `.jpeg`, `.bmp`, `.heif`

## Keyboard Shortcuts

The tool is optimized for efficient usage with several keyboard shortcuts:

- **A**: Load previous image.
- **D**: Load next image.
- **R**: Reset annotations on the current image.
- **1**: Apply the LMG skeleton for annotation.
- **2**: Apply the Rifle skeleton for annotation.
- **Ctrl + Z**: Undo last annotation change.
- **Ctrl + Y**: Redo last undone change.
- **Ctrl + S**: Save annotations.
- **Ctrl + Shift + I**: Select image folder.
- **Ctrl + Shift + S**: Select save folder for annotations.
- **Ctrl + A**: Toggle auto-save annotations.
- **Ctrl + E**: Extract frames from video.
- **Ctrl + Shift + R**: Resize images.
- **. (Period)**: Open the keyboard shortcuts menu.

## Installation

### Running the Executable (.exe)

If you do not wish to set up a Python environment, you can simply download the executable file from the repository and run it directly.

### Running from Source Code

1. **Clone the repository:**

    ```bash
    git clone https://github.com/msuthar7/Gun-Key-Point-Annotation-Tool.git
    cd Gun-Key-Point-Annotation-Tool
    ```

2. **Install dependencies:**

    To run the tool from the source code, you'll need Python 3.12 and the required libraries. Install them by running:

    ```bash
    pip install -r requirements.txt
    ```

3. **Run the tool:**

    After the dependencies are installed, run the tool using:

    ```bash
    python KeypointAnnotationTool.py
    ```

## Image Annotation Format

Annotations are saved in **YOLO format** for pose estimation. For each annotated image, a `.txt` file is generated with the following structure:

```plaintext
<class-index> <center-x> <center-y> <width> <height> <px1> <py1> ... <pxn> <pyn>
```

Where:

- **class-index**: Class identifier (e.g., 0 for LMG, 1 for Rifle).
- **center-x, center-y, width, height**: Bounding box coordinates (normalized).
- **px1, py1, ..., pxn, pyn**: Keypoints (normalized coordinates).

## Example Workflow

### 1. Image Folder Selection:
Choose the folder containing your images by clicking 'Select Image Folder' or pressing `Ctrl + Shift + I`.

### 2.  Annotation Folder Selection:

Choose the folder to save annotations by clicking 'Select Save Folder' or pressing `Ctrl + Shift + S`.

### 3.  Annotate:

Begin annotating keypoints by selecting either the **LMG** or **Rifle** skeleton and adjusting the keypoints for each part.

### 4.  Save Annotations:

Save the annotations manually or let auto-save handle it. Files are saved in **YOLO format**.

### 5.  Export Frames:

Use the frame extraction tool to create individual images from a video file for further annotation.

### 6.  Resize Images:

Batch resize images with the built-in resize tool.

## Dependencies

- **Python 3.12**
- **PyQt5**: For the graphical user interface.
- **OpenCV**: For image processing and display.
- **NumPy**: For handling arrays and numerical operations.

Install these dependencies using:

```bash
pip install -r requirements.txt
