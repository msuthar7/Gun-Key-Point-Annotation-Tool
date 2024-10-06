import sys
import cv2
import numpy as np
import os
from PyQt5.QtWidgets import (
    QApplication, QLabel, QMainWindow, QPushButton, QFileDialog,
    QVBoxLayout, QWidget, QHBoxLayout, QScrollArea, QFrame, QCheckBox,
    QDialog, QLineEdit, QMessageBox, QProgressBar, QSizePolicy
)
from PyQt5.QtGui import (
    QPixmap, QImage, QPainter, QPen
)
from PyQt5.QtCore import Qt, QPoint, QTimer, pyqtSignal

# List of parts to annotate, including left and right bipod
parts = [
    "butt", "pistol grip", "trigger", "cover", "rear sight",
    "barrel jacket", "left bipod", "right bipod", "front handguard", "barrel"
]

# Connections between parts for LMG
connections = [
    ("butt", "cover"),
    ("cover", "pistol grip"),
    ("cover", "trigger"),
    ("cover", "rear sight"),
    ("rear sight", "barrel jacket"),
    ("barrel jacket", "left bipod"),
    ("barrel jacket", "right bipod")
]

# Rifle Skeleton parts and connections
rifle_connections = [
    ("butt", "rear sight"),
    ("rear sight", "pistol grip"),
    ("rear sight", "trigger"),
    ("rear sight", "front handguard"),
    ("front handguard", "barrel")
]

class ElidedLabel(QLabel):
    """Custom QLabel that displays elided text with an ellipsis when it exceeds the available width."""
    def __init__(self, text='', parent=None):
        super().__init__(text, parent)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setWordWrap(False)
        self.setTextInteractionFlags(Qt.TextSelectableByMouse)

    def paintEvent(self, event):
        painter = QPainter(self)
        metrics = painter.fontMetrics()
        elided_text = metrics.elidedText(self.text(), Qt.ElideMiddle, self.width())
        painter.drawText(self.rect(), self.alignment(), elided_text)

class Skeleton:
    def __init__(self, default_positions, skeleton_id, skeleton_type):
        self.id = skeleton_id
        self.annotations = default_positions.copy()
        self.annotation_history = []
        self.redo_stack = []
        self.selected_keypoint = None
        self.skeleton_type = skeleton_type  # Add skeleton_type to distinguish between LMG and Rifle

class ImageLabel(QLabel):
    point_clicked = pyqtSignal(int, int)
    keypoint_selected = pyqtSignal(Skeleton, str)
    keypoint_moved = pyqtSignal(Skeleton, str, int, int)

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window  # Store reference to the main window
        self.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.image = None
        self.zoom_level = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.selected_skeleton = None
        self.selected_keypoint = None
        self.dragging_keypoint = False
        self.setFocusPolicy(Qt.StrongFocus)  # To receive key events

    def set_image(self, image):
        self.image = image

    def set_zoom_level(self, zoom_level):
        self.zoom_level = zoom_level

    def set_offsets(self, offset_x, offset_y):
        self.offset_x = offset_x
        self.offset_y = offset_y

    def mousePressEvent(self, event):
        if self.image is not None:
            x_click = (event.x() - self.offset_x) / self.zoom_level
            y_click = (event.y() - self.offset_y) / self.zoom_level

            # Check if the click is on a keypoint of any skeleton
            clicked_on_keypoint = False
            for skeleton in self.main_window.skeletons:
                for part, coords in skeleton.annotations.items():
                    if coords is not None:
                        x_anno, y_anno = coords
                        distance = np.hypot(x_click - x_anno, y_click - y_anno)
                        if distance <= 10:  # 10 pixels tolerance
                            self.selected_skeleton = skeleton
                            self.selected_keypoint = part
                            clicked_on_keypoint = True
                            self.dragging_keypoint = True
                            self.keypoint_selected.emit(skeleton, part)
                            break
                if clicked_on_keypoint:
                    break

    def mouseMoveEvent(self, event):
        if self.dragging_keypoint and self.selected_keypoint and self.selected_skeleton:
            x_move = (event.x() - self.offset_x) / self.zoom_level
            y_move = (event.y() - self.offset_y) / self.zoom_level

            # Ensure coordinates remain within image bounds
            height, width, _ = self.image.shape
            x_move = max(0, min(int(x_move), width - 1))
            y_move = max(0, min(int(y_move), height - 1))

            # Update the position of the selected keypoint
            old_coords = self.selected_skeleton.annotations[self.selected_keypoint]
            self.selected_skeleton.annotations[self.selected_keypoint] = (x_move, y_move)
            self.keypoint_moved.emit(self.selected_skeleton, self.selected_keypoint, x_move, y_move)

            # Record the action for undo
            self.main_window.annotation_history.append(('move_keypoint', self.selected_skeleton, self.selected_keypoint, old_coords, (x_move, y_move)))
            self.main_window.redo_stack.clear()
            self.update()

    def mouseReleaseEvent(self, event):
        self.dragging_keypoint = False

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.image is not None:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            # Apply zoom and offsets
            painter.scale(self.zoom_level, self.zoom_level)
            painter.translate(self.offset_x / self.zoom_level, self.offset_y / self.zoom_level)

            # Draw all skeletons
            for skeleton in self.main_window.skeletons:
                # Draw keypoints
                for part, coords in skeleton.annotations.items():
                    pen = QPen(Qt.red, 6)
                    painter.setPen(pen)
                    if coords is not None:
                        x, y = coords
                        painter.drawEllipse(QPoint(int(x), int(y)), 5, 5)

                        # Set color for text
                        text_pen = QPen(Qt.white)
                        painter.setPen(text_pen)

                        # Draw the annotation text
                        painter.drawText(QPoint(int(x) + 10, int(y) - 10), f"S{ skeleton.id }:{ part }")

                # Draw skeleton lines
                self.draw_skeleton(painter, skeleton)

    def draw_skeleton(self, painter, skeleton):
        # Connect the points to form a gun skeleton
        pen = QPen(Qt.green, 2)
        painter.setPen(pen)
        if skeleton.skeleton_type == 'LMG':
            conn = self.main_window.connections
        else:
            conn = self.main_window.rifle_connections

        for part1, part2 in conn:
            if skeleton.annotations.get(part1) is not None and skeleton.annotations.get(part2) is not None:
                x1, y1 = skeleton.annotations[part1]
                x2, y2 = skeleton.annotations[part2]
                painter.drawLine(QPoint(int(x1), int(y1)), QPoint(int(x2), int(y2)))

class KeypointAnnotationTool(QMainWindow):
    def __init__(self):
        super().__init__()
        self.image = None
        self.clone = None
        self.zoom_level = 1.0  # Initialize zoom level
        self.dragging = False
        self.last_drag_pos = QPoint()
        self.offset_x = 0  # Offset for dragging
        self.offset_y = 0
        self.save_folder = None  # Folder to save annotations
        self.auto_save = False  # Auto-save toggle
        self.skeletons = []  # List of Skeleton instances
        self.deleted_skeleton_ids = set()  # Track deleted skeleton IDs to reuse them
        self.annotation_history = []  # Global history for undo/redo
        self.redo_stack = []
        self.selected_skeleton = None
        self.selected_keypoint = None
        self.image_file_paths = []  # List of image file paths
        self.current_image_index = -1  # Index of the current image
        self.current_skeleton_type = 'LMG'  # Default skeleton type

        # Make connections accessible to ImageLabel
        self.connections = connections
        self.rifle_connections = rifle_connections

        self.initUI()

    def initUI(self):
        # Window properties
        self.setWindowTitle('Gun Keypoint Annotation Tool')
        self.setGeometry(100, 100, 1200, 800)

        # Create main layout
        self.main_layout = QHBoxLayout()

        # Create left-side control panel for label selection, load, reset
        self.left_panel = QVBoxLayout()

        # Button to select image folder
        self.select_folder_button = QPushButton('Select Image Folder', self)
        self.select_folder_button.clicked.connect(self.select_image_folder)
        self.left_panel.addWidget(self.select_folder_button)

        # Label to display selected image folder path
        self.image_folder_label = ElidedLabel('No image folder selected', self)
        self.image_folder_label.setMaximumWidth(200)  # Set maximum width
        self.left_panel.addWidget(self.image_folder_label)

        # Add a section label for image options
        self.left_panel.addWidget(QLabel('Image Options'))

        # Button to load the next image
        self.next_image_button = QPushButton('Next Image', self)
        self.next_image_button.clicked.connect(self.load_next_image)
        self.left_panel.addWidget(self.next_image_button)

        # Button to load the previous image
        self.prev_image_button = QPushButton('Previous Image', self)
        self.prev_image_button.clicked.connect(self.load_previous_image)
        self.left_panel.addWidget(self.prev_image_button)

        # Add a section label for annotation options
        self.left_panel.addWidget(QLabel('Annotation Options'))

        # Add option to select LMG Skeleton
        self.lmg_skeleton_button = QPushButton('LMG Skeleton', self)
        self.lmg_skeleton_button.clicked.connect(lambda: self.set_skeleton_type('LMG'))
        self.left_panel.addWidget(self.lmg_skeleton_button)

        # Add option to select Rifle Skeleton
        self.rifle_skeleton_button = QPushButton('Rifle Skeleton', self)
        self.rifle_skeleton_button.clicked.connect(lambda: self.set_skeleton_type('Rifle'))
        self.left_panel.addWidget(self.rifle_skeleton_button)

        # Add a section label for actions
        self.left_panel.addWidget(QLabel('Actions'))

        # Button to reset annotations
        self.reset_button = QPushButton('Reset', self)
        self.reset_button.clicked.connect(self.reset_annotations)
        self.left_panel.addWidget(self.reset_button)

        # Button to undo last action
        self.undo_button = QPushButton('Undo', self)
        self.undo_button.clicked.connect(self.undo_action)
        self.left_panel.addWidget(self.undo_button)

        # Button to redo last undone action
        self.redo_button = QPushButton('Redo', self)
        self.redo_button.clicked.connect(self.redo_action)
        self.left_panel.addWidget(self.redo_button)

        # Add the zoom label
        self.zoom_label = QLabel('Zoom: 100%', self)
        self.left_panel.addWidget(self.zoom_label)

        # Checkbox for auto-save image option
        self.auto_save_checkbox = QCheckBox('Auto Save Annotations', self)
        self.auto_save_checkbox.stateChanged.connect(self.toggle_auto_save)
        self.left_panel.addWidget(self.auto_save_checkbox)

        # Add a section to display save folder path
        self.left_panel.addWidget(QLabel('Save Folder Path'))

        self.folder_label = ElidedLabel('No save folder selected', self)
        self.folder_label.setMaximumWidth(200)  # Set maximum width
        self.left_panel.addWidget(self.folder_label)

        # Button to select folder to save
        self.folder_button = QPushButton('Select Save Folder', self)
        self.folder_button.clicked.connect(self.select_save_folder)
        self.left_panel.addWidget(self.folder_button)

        # Button to save annotations
        self.save_button = QPushButton('Save Annotations', self)
        self.save_button.clicked.connect(self.save_annotations)
        self.left_panel.addWidget(self.save_button)

        # Button to extract frames from video
        self.extract_frames_button = QPushButton('Extract Frames', self)
        self.extract_frames_button.clicked.connect(self.open_extract_frames_dialog)
        self.left_panel.addWidget(self.extract_frames_button)

        # Button to resize images
        self.resize_button = QPushButton('Resize Images', self)
        self.resize_button.clicked.connect(self.open_resize_dialog)
        self.left_panel.addWidget(self.resize_button)

        # Add a section label for accessibility
        self.left_panel.addWidget(QLabel('Accessibility'))

        # Button to show keyboard shortcuts
        self.keyboard_shortcuts_button = QPushButton('Keyboard Shortcuts', self)
        self.keyboard_shortcuts_button.clicked.connect(self.show_keyboard_shortcuts)
        self.left_panel.addWidget(self.keyboard_shortcuts_button)

        # Add the left panel to the main layout
        self.left_panel_container = QWidget()
        self.left_panel_container.setLayout(self.left_panel)
        self.main_layout.addWidget(self.left_panel_container)

        # Create the image label inside a scrollable area
        self.scroll_area = QScrollArea(self)
        self.image_label = ImageLabel(self)  # Pass 'self' as 'main_window'
        # Connect signals
        self.image_label.keypoint_selected.connect(self.keypoint_selected)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.image_label)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.main_layout.addWidget(self.scroll_area)

        # Create a central widget for the main layout
        self.central_widget = QWidget()
        self.central_widget.setLayout(self.main_layout)
        self.setCentralWidget(self.central_widget)

        self.show()

    def open_extract_frames_dialog(self):
        dialog = ExtractFramesDialog(self)
        dialog.exec_()

    def open_resize_dialog(self):
        dialog = ResizeDialog(self)
        dialog.exec_()

    def select_image_folder(self):
        # Open a dialog to select the folder containing images
        folder_path = QFileDialog.getExistingDirectory(
            self, 'Select Image Folder')
        if folder_path:
            self.image_folder_path = folder_path
            self.image_folder_label.setText(f"Image Folder: {self.image_folder_path}")
            self.image_folder_label.setToolTip(self.image_folder_label.text())

            # Get list of image files in the folder
            supported_formats = ('.png', '.jpg', '.jpeg', '.bmp', '.heif')
            self.image_file_paths = [os.path.join(self.image_folder_path, f)
                                     for f in os.listdir(self.image_folder_path)
                                     if f.lower().endswith(supported_formats)]
            self.image_file_paths.sort()  # Sort the file list

            if self.image_file_paths:
                self.current_image_index = 0
                self.load_image()
            else:
                self.show_toast("No images found in the selected folder.")
        else:
            self.image_folder_label.setText("No image folder selected")
            self.image_folder_label.setToolTip(self.image_folder_label.text())

    def load_image(self):
        if 0 <= self.current_image_index < len(self.image_file_paths):
            self.image_file_path = self.image_file_paths[self.current_image_index]
            self.image = cv2.imread(self.image_file_path)
            self.clone = self.image.copy()
            self.zoom_level = 1.0  # Reset zoom when a new image is loaded
            self.offset_x = 0
            self.offset_y = 0
            self.skeletons = []
            self.deleted_skeleton_ids = set()
            self.annotation_history = []
            self.redo_stack = []
            self.display_image()
            self.image_label.set_image(self.clone)
            self.image_label.set_zoom_level(self.zoom_level)
            self.image_label.set_offsets(self.offset_x, self.offset_y)
            self.image_label.update()
            self.setWindowTitle(f"Annotating: {os.path.basename(self.image_file_path)}")

            if self.save_folder:
                # Load existing annotations if they exist
                self.load_annotations()
        else:
            self.show_toast("No images to load.")

    def load_next_image(self):
        if not self.image_file_paths or self.image is None:
            self.show_toast("No Image Loaded")
            return

        # Save current annotations if auto-save is enabled
        if self.auto_save:
            self.save_annotations()

        self.current_image_index += 1
        if self.current_image_index >= len(self.image_file_paths):
            self.current_image_index = 0  # Loop back to the first image
        self.load_image()

    def load_previous_image(self):
        if not self.image_file_paths or self.image is None:
            self.show_toast("No Image Loaded")
            return

        # Save current annotations if auto-save is enabled
        if self.auto_save:
            self.save_annotations()

        self.current_image_index -= 1
        if self.current_image_index < 0:
            self.current_image_index = len(self.image_file_paths) - 1  # Go to the last image
        self.load_image()

    def set_skeleton_type(self, skeleton_type):
        """Set the type of skeleton (LMG or Rifle) to annotate and add it to the image."""
        if self.image is None:
            self.show_toast("No Image Loaded")
            return
        self.current_skeleton_type = skeleton_type
        self.show_toast(f"Selected {skeleton_type} Skeleton.")
        self.add_new_skeleton()

    def add_new_skeleton(self):
        # Initialize annotations with default positions (centered)
        if self.image is not None:
            skeleton_id = self.get_next_skeleton_id()
            height, width, _ = self.image.shape
            center_x = width // 2
            center_y = height // 2
            if self.current_skeleton_type == 'LMG':
                default_positions = {
                    "butt": (center_x - 100, center_y),
                    "pistol grip": (center_x - 50, center_y + 50),
                    "trigger": (center_x, center_y + 20),
                    "cover": (center_x, center_y),
                    "rear sight": (center_x + 50, center_y - 30),
                    "barrel jacket": (center_x + 100, center_y),
                    "left bipod": (center_x + 150, center_y + 50),
                    "right bipod": (center_x + 150, center_y - 50)
                }
            else:  # Rifle skeleton
                default_positions = {
                    "butt": (center_x - 100, center_y),
                    "rear sight": (center_x - 50, center_y - 30),
                    "pistol grip": (center_x - 10, center_y + 50),
                    "trigger": (center_x, center_y + 20),
                    "front handguard": (center_x + 50, center_y),
                    "barrel": (center_x + 100, center_y)
                }

            # Pass the skeleton_type to the Skeleton constructor
            skeleton = Skeleton(default_positions, skeleton_id, self.current_skeleton_type)
            self.skeletons.append(skeleton)
            self.selected_skeleton = skeleton
            # Record the action for undo
            self.annotation_history.append(('add_skeleton', skeleton))
            # Clear redo stack
            self.redo_stack.clear()
            # Update display
            self.image_label.update()
        else:
            self.show_toast("Please load an image first.")

    def get_next_skeleton_id(self):
        # Reuse deleted skeleton IDs or increment if no deleted IDs
        existing_ids = {skeleton.id for skeleton in self.skeletons}
        all_ids = set(range(1, len(self.skeletons) + len(self.deleted_skeleton_ids) + 2))
        available_ids = all_ids - existing_ids
        return min(available_ids)

    def display_image(self):
        if self.image is not None:
            height, width, channels = self.image.shape

            # Apply the zoom level to the image size
            zoomed_width = int(width * self.zoom_level)
            zoomed_height = int(height * self.zoom_level)

            # Resize the image based on zoom level
            resized_image = cv2.resize(
                self.image, (zoomed_width, zoomed_height), interpolation=cv2.INTER_AREA)
            bytes_per_line = channels * zoomed_width
            q_image = QImage(resized_image.data, zoomed_width, zoomed_height,
                             bytes_per_line, QImage.Format_BGR888)
            pixmap = QPixmap.fromImage(q_image)
            self.image_label.setPixmap(pixmap)
            self.image_label.adjustSize()  # Ensure the label resizes to the pixmap size

            # Update image label properties
            self.image_label.set_zoom_level(self.zoom_level)
            self.image_label.set_offsets(self.offset_x, self.offset_y)

            # Adjust the scroll area based on zoom and drag offsets
            self.image_label.move(self.offset_x, self.offset_y)
            self.image_label.update()

    def keypoint_selected(self, skeleton, part):
        self.selected_skeleton = skeleton
        self.selected_keypoint = part

    def reset_annotations(self):
        if self.image is None:
            self.show_toast("No Image Loaded")
            return

        # Record the current state for undo
        self.annotation_history.append(('reset', self.skeletons.copy()))
        # Clear redo stack
        self.redo_stack.clear()
        # Reset annotations
        self.skeletons = []
        self.deleted_skeleton_ids = set()
        self.selected_skeleton = None
        self.selected_keypoint = None

        # Delete the annotation file if auto-save is enabled
        if self.auto_save and self.save_folder:
            image_name = os.path.basename(self.image_file_path)
            base_name = os.path.splitext(image_name)[0]
            label_file_path = os.path.join(self.save_folder, f"{base_name}.txt")
            if os.path.exists(label_file_path):
                os.remove(label_file_path)
                print(f"Annotation file {label_file_path} deleted due to reset.")

        self.image_label.update()

    def undo_action(self):
        if self.image is None:
            self.show_toast("No Image Loaded")
            return

        if self.annotation_history:
            action = self.annotation_history.pop()
            self.redo_stack.append(action)
            action_type = action[0]

            if action_type == 'add_skeleton':
                skeleton = action[1]
                self.skeletons.remove(skeleton)
                self.deleted_skeleton_ids.add(skeleton.id)
            elif action_type == 'move_keypoint':
                skeleton, part, old_coords, new_coords = action[1], action[2], action[3], action[4]
                skeleton.annotations[part] = old_coords
            elif action_type == 'delete_keypoint':
                skeleton, part, coords = action[1], action[2], action[3]
                skeleton.annotations[part] = coords
            elif action_type == 'reset':
                self.skeletons = action[1]
                self.deleted_skeleton_ids = set()
            self.image_label.update()
        else:
            self.show_toast("No actions to undo.")

    def redo_action(self):
        if self.image is None:
            self.show_toast("No Image Loaded")
            return

        if self.redo_stack:
            action = self.redo_stack.pop()
            self.annotation_history.append(action)
            action_type = action[0]

            if action_type == 'add_skeleton':
                skeleton = action[1]
                self.skeletons.append(skeleton)
                self.deleted_skeleton_ids.discard(skeleton.id)
            elif action_type == 'move_keypoint':
                skeleton, part, old_coords, new_coords = action[1], action[2], action[3], action[4]
                skeleton.annotations[part] = new_coords
            elif action_type == 'delete_keypoint':
                skeleton, part, coords = action[1], action[2], action[3]
                skeleton.annotations[part] = None
            elif action_type == 'reset':
                self.skeletons = []
                self.deleted_skeleton_ids = set()
            self.image_label.update()
        else:
            self.show_toast("No actions to redo.")

    def select_save_folder(self):
        # Open a dialog to select the folder for saving annotations
        self.save_folder = QFileDialog.getExistingDirectory(
            self, 'Select Folder to Save Annotations')
        if self.save_folder:
            self.folder_label.setText(f"Save Folder: {self.save_folder}")
            self.folder_label.setToolTip(self.folder_label.text())
        else:
            self.folder_label.setText("No save folder selected")
            self.folder_label.setToolTip(self.folder_label.text())

    def toggle_auto_save(self, state):
        # Toggle auto-save functionality
        self.auto_save = state == Qt.Checked
        message = 'Auto Save Enabled' if self.auto_save else 'Auto Save Disabled'
        self.show_toast(message)

    def show_keyboard_shortcuts(self):
        shortcuts_text = (
            "Keyboard Shortcuts:\n\n"
            "A: Previous Image\n"
            "D: Next Image\n"
            "R: Reset Annotations\n"
            "1: Add LMG Skeleton\n"
            "2: Add Rifle Skeleton\n"
            "Ctrl + Z: Undo\n"
            "Ctrl + Y: Redo\n"
            "Ctrl + S: Save Annotations\n"
            "Ctrl + Shift + I: Select Image Folder\n"
            "Ctrl + Shift + S: Select Save Folder\n"
            "Ctrl + A: Toggle Auto Save Annotations\n"
            ". (Period): Show Keyboard Shortcuts\n"
            "Ctrl + E: Extract Frames\n"
            "Ctrl + Shift + R: Resize Images\n"
        )
        QMessageBox.information(self, "Keyboard Shortcuts", shortcuts_text)

    def show_toast(self, message):
        toast = QLabel(message, self)
        toast.setStyleSheet("background-color: black; color: white; padding: 10px; border-radius: 5px;")
        toast.adjustSize()
        # Position the toast in the center bottom of the main window
        toast_width = toast.width()
        toast_height = toast.height()
        x = (self.width() - toast_width) // 2
        y = self.height() - toast_height - 50
        toast.move(x, y)
        toast.show()

        # Hide the toast after 2 seconds
        QTimer.singleShot(2000, toast.hide)

    def save_annotations(self):
        if not self.save_folder:
            self.show_toast("No Save Folder Selected")
            return

        if self.image is not None and self.save_folder:
            if not self.skeletons:
                # Do not save if there are no annotations
                print("No annotations to save.")
                # Remove existing annotation file if it exists
                image_name = os.path.basename(self.image_file_path)
                base_name = os.path.splitext(image_name)[0]
                label_file_path = os.path.join(self.save_folder, f"{base_name}.txt")
                if os.path.exists(label_file_path):
                    os.remove(label_file_path)
                    print(f"Removed existing annotation file {label_file_path} due to no annotations.")
                return

            image_name = os.path.basename(self.image_file_path)
            save_yolo_format(
                self.save_folder, image_name, self.skeletons,
                self.image.shape[1], self.image.shape[0]
            )
            self.show_toast("Annotations saved.")
        else:
            self.show_toast("No image loaded.")

    def load_annotations(self):
        # Load annotations from a file if it exists
        if not self.save_folder:
            return
        image_name = os.path.basename(self.image_file_path)
        base_name = os.path.splitext(image_name)[0]
        label_file_path = os.path.join(self.save_folder, f"{base_name}.txt")
        if os.path.exists(label_file_path):
            with open(label_file_path, 'r') as label_file:
                lines = label_file.readlines()
                self.skeletons = []  # Clear existing skeletons
                for line in lines:
                    # Parse each line according to YOLO format
                    parts = line.strip().split()
                    if len(parts) < 5:
                        continue  # Invalid line
                    class_index = int(parts[0])
                    bbox_center_x = float(parts[1])
                    bbox_center_y = float(parts[2])
                    bbox_width = float(parts[3])
                    bbox_height = float(parts[4])
                    keypoints = parts[5:]
                    # Create skeleton based on class_index
                    if class_index == 0:
                        skeleton_type = 'LMG'
                        skeleton_parts = ["butt", "pistol grip", "trigger", "cover", "rear sight",
                                          "barrel jacket", "left bipod", "right bipod"]
                    else:
                        skeleton_type = 'Rifle'
                        skeleton_parts = ["butt", "rear sight", "pistol grip", "trigger", "front handguard", "barrel"]
                    # Initialize annotations
                    annotations = {}
                    num_keypoints = len(skeleton_parts)
                    for i in range(num_keypoints):
                        idx = i * 2
                        if idx + 1 < len(keypoints):
                            x_str, y_str = keypoints[idx], keypoints[idx + 1]
                            x = float(x_str)
                            y = float(y_str)
                            if x >= 0 and y >= 0:
                                # Denormalize coordinates
                                x *= self.image.shape[1]
                                y *= self.image.shape[0]
                                annotations[skeleton_parts[i]] = (x, y)
                            else:
                                annotations[skeleton_parts[i]] = None
                    # Create Skeleton instance
                    skeleton_id = self.get_next_skeleton_id()
                    skeleton = Skeleton(annotations, skeleton_id, skeleton_type)
                    self.skeletons.append(skeleton)
                self.image_label.update()

    def wheelEvent(self, event):
        # Zoom in or out based on the wheel scroll direction
        if event.angleDelta().y() > 0:
            self.zoom_level += 0.1  # Zoom in
        else:
            self.zoom_level = max(0.1, self.zoom_level - 0.1)  # Zoom out, minimum zoom of 0.1

        # Update the zoom label
        zoom_percentage = int(self.zoom_level * 100)
        self.zoom_label.setText(f'Zoom: {zoom_percentage}%')

        # Update the display with the new zoom level
        self.display_image()

    def mousePressEvent(self, event):
        # Handle drag start
        if event.modifiers() == Qt.ControlModifier:
            self.dragging = True
            self.last_drag_pos = event.pos()

    def mouseMoveEvent(self, event):
        # Handle dragging
        if self.dragging:
            delta = event.pos() - self.last_drag_pos
            self.offset_x += delta.x()
            self.offset_y += delta.y()
            self.last_drag_pos = event.pos()
            self.display_image()

    def mouseReleaseEvent(self, event):
        # End dragging
        self.dragging = False

    def keyPressEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()

        if key == Qt.Key_Delete:
            if self.selected_skeleton and self.selected_keypoint:
                # Delete the selected keypoint
                coords = self.selected_skeleton.annotations[self.selected_keypoint]
                self.selected_skeleton.annotations[self.selected_keypoint] = None
                print(f"Keypoint '{self.selected_keypoint}' deleted from Skeleton {self.selected_skeleton.id}.")
                # Record the action for undo
                self.annotation_history.append(('delete_keypoint', self.selected_skeleton, self.selected_keypoint, coords))
                # Clear redo stack
                self.redo_stack.clear()
                self.selected_keypoint = None
                self.image_label.update()

        elif key == Qt.Key_A and not modifiers:
            # 'A' key for previous image
            self.load_previous_image()

        elif key == Qt.Key_D and not modifiers:
            # 'D' key for next image
            self.load_next_image()

        elif key == Qt.Key_R and not modifiers:
            # 'R' key for reset
            self.reset_annotations()

        elif key == Qt.Key_1 and not modifiers:
            # '1' key for LMG Skeleton
            self.set_skeleton_type('LMG')

        elif key == Qt.Key_2 and not modifiers:
            # '2' key for Rifle Skeleton
            self.set_skeleton_type('Rifle')

        elif key == Qt.Key_Z and modifiers == Qt.ControlModifier:
            # Ctrl + 'Z' for undo
            self.undo_action()

        elif key == Qt.Key_Y and modifiers == Qt.ControlModifier:
            # Ctrl + 'Y' for redo
            self.redo_action()

        elif key == Qt.Key_S and modifiers == Qt.ControlModifier:
            # Ctrl + 'S' for save annotations
            self.save_annotations()

        elif key == Qt.Key_I and modifiers == (Qt.ControlModifier | Qt.ShiftModifier):
            # Ctrl + Shift + 'I' for select image folder
            self.select_image_folder()

        elif key == Qt.Key_S and modifiers == (Qt.ControlModifier | Qt.ShiftModifier):
            # Ctrl + Shift + 'S' for select save folder
            self.select_save_folder()

        elif key == Qt.Key_A and modifiers == Qt.ControlModifier:
            # Ctrl + 'A' for enabling/disabling auto save annotations
            current_state = self.auto_save_checkbox.isChecked()
            self.auto_save_checkbox.setChecked(not current_state)
            self.toggle_auto_save(Qt.Checked if not current_state else Qt.Unchecked)

        elif key == Qt.Key_Period and not modifiers:
            # '.' key to open keyboard shortcuts
            self.show_keyboard_shortcuts()

        elif key == Qt.Key_E and modifiers == Qt.ControlModifier:
            # Ctrl + 'E' for extract frames
            self.open_extract_frames_dialog()

        elif key == Qt.Key_R and modifiers == (Qt.ControlModifier | Qt.ShiftModifier):
            # Ctrl + Shift + 'R' for resize images
            self.open_resize_dialog()

def save_yolo_format(save_folder, image_name, skeletons, image_width, image_height):
    """
    Save annotations in YOLO format for pose estimation.
    Args:
    - save_folder: Folder where the annotations should be saved.
    - image_name: Name of the image file.
    - skeletons: List of skeletons with keypoint annotations.
    - image_width: The width of the image.
    - image_height: The height of the image.
    """
    # Create the path for the corresponding .txt file
    base_name = os.path.splitext(image_name)[0]
    label_file_path = os.path.join(save_folder, f"{base_name}.txt")

    # List to store the YOLO format data for each object
    yolo_data = []

    # Loop through all skeletons
    for skeleton in skeletons:
        # Initialize variables for bounding box
        keypoints = []
        xs = []
        ys = []

        # Assign class index based on the skeleton type
        if skeleton.skeleton_type == 'LMG':
            skeleton_parts = ["butt", "pistol grip", "trigger", "cover", "rear sight",
                              "barrel jacket", "left bipod", "right bipod"]
            class_index = 0  # LMG class index
        else:
            skeleton_parts = ["butt", "rear sight", "pistol grip", "trigger", "front handguard", "barrel"]
            class_index = 1  # Rifle class index

        # Process keypoints
        for part in skeleton_parts:
            coords = skeleton.annotations.get(part)
            if coords is not None:
                x, y = coords

                # Normalize the keypoint coordinates
                normalized_x = x / image_width
                normalized_y = y / image_height

                # Collect coordinates for bounding box calculation
                xs.append(normalized_x)
                ys.append(normalized_y)

                # Append normalized keypoints to list
                keypoints.extend([f"{normalized_x:.6f}", f"{normalized_y:.6f}"])
            else:
                # If keypoint is missing, append -1 -1
                keypoints.extend(["-1", "-1"])

        # If there are valid keypoints, calculate bounding box
        if xs and ys:
            min_x = min(xs)
            max_x = max(xs)
            min_y = min(ys)
            max_y = max(ys)

            # Calculate bounding box center and size
            bbox_center_x = (min_x + max_x) / 2
            bbox_center_y = (min_y + max_y) / 2
            bbox_width = max_x - min_x
            bbox_height = max_y - min_y

            # Format: <class-index> <x> <y> <width> <height> <px1> <py1> ... <pxn> <pyn>
            yolo_format_line = f"{class_index} {bbox_center_x:.6f} {bbox_center_y:.6f} " \
                               f"{bbox_width:.6f} {bbox_height:.6f} " + " ".join(keypoints)

            # Append the object information in YOLO format
            yolo_data.append(yolo_format_line)

    # If there is data to save, write to file
    if yolo_data:
        with open(label_file_path, 'w') as label_file:
            label_file.write("\n".join(yolo_data))
        print(f"Annotations saved to {label_file_path}.")
    else:
        # Do not save an empty file
        print(f"No annotations to save for {image_name}.")
        # Optional: Remove existing annotation file if it exists
        if os.path.exists(label_file_path):
            os.remove(label_file_path)
            print(f"Removed existing annotation file {label_file_path} due to no annotations.")

class ExtractFramesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Extract Frames from Video')
        self.setModal(True)
        self.video_file_path = ''
        self.output_folder = ''
        self.fps = 1  # Default FPS
        self.stop_requested = False  # Flag to handle stopping
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        # FPS input
        fps_layout = QHBoxLayout()
        fps_label = QLabel('Frames per Second (FPS):')
        self.fps_input = QLineEdit()
        self.fps_input.setText('1')  # Default FPS value
        fps_layout.addWidget(fps_label)
        fps_layout.addWidget(self.fps_input)
        layout.addLayout(fps_layout)

        # Video file selection
        video_layout = QHBoxLayout()
        self.video_button = QPushButton('Select Video File')
        self.video_button.clicked.connect(self.select_video_file)
        self.video_label = QLabel('No video file selected')
        video_layout.addWidget(self.video_button)
        video_layout.addWidget(self.video_label)
        layout.addLayout(video_layout)

        # Output folder selection
        output_layout = QHBoxLayout()
        self.output_button = QPushButton('Select Output Folder')
        self.output_button.clicked.connect(self.select_output_folder)
        self.output_label = QLabel('No output folder selected')
        output_layout.addWidget(self.output_button)
        output_layout.addWidget(self.output_label)
        layout.addLayout(output_layout)

        # Progress bar for frame extraction
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # Extract frames button
        button_layout = QHBoxLayout()
        self.extract_button = QPushButton('Extract Frames')
        self.extract_button.clicked.connect(self.extract_frames)
        self.stop_button = QPushButton('Stop')
        self.stop_button.clicked.connect(self.stop_extraction)
        button_layout.addWidget(self.extract_button)
        button_layout.addWidget(self.stop_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def select_video_file(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(
            self, 'Select Video File', '', 'Videos (*.mp4 *.avi *.mov *.mkv)', options=options)
        if file_path:
            self.video_file_path = file_path
            self.video_label.setText(os.path.basename(file_path))

    def select_output_folder(self):
        folder_path = QFileDialog.getExistingDirectory(
            self, 'Select Output Folder')
        if folder_path:
            self.output_folder = folder_path
            self.output_label.setText(folder_path)

    def stop_extraction(self):
        self.stop_requested = True

    def extract_frames(self):
        # Validate inputs
        if not self.video_file_path:
            QMessageBox.warning(self, 'Error', 'Please select a video file.')
            return
        if not self.output_folder:
            QMessageBox.warning(self, 'Error', 'Please select an output folder.')
            return
        try:
            fps = float(self.fps_input.text())
            if fps <= 0:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, 'Error', 'Please enter a valid FPS value.')
            return

        # Proceed to extract frames
        cap = cv2.VideoCapture(self.video_file_path)
        video_fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_interval = int(round(video_fps / fps))

        frame_count = 0
        saved_frame_count = 0
        success, frame = cap.read()

        self.progress_bar.setMaximum(total_frames)
        self.stop_requested = False  # Reset stop flag

        while success and not self.stop_requested:
            if frame_count % frame_interval == 0:
                # Save frame as image
                frame_filename = f"frame_{saved_frame_count:05d}.jpg"
                frame_path = os.path.join(self.output_folder, frame_filename)
                cv2.imwrite(frame_path, frame)
                saved_frame_count += 1

            frame_count += 1
            self.progress_bar.setValue(frame_count)
            QApplication.processEvents()  # Keep the GUI responsive
            success, frame = cap.read()

        cap.release()
        if self.stop_requested:
            QMessageBox.information(self, 'Stopped', 'Frame extraction stopped.')
        else:
            QMessageBox.information(self, 'Success', f'Extracted {saved_frame_count} frames.')
        self.close()

class ResizeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Resize Images')
        self.width = None
        self.height = None
        self.keep_aspect_ratio = False
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        # Input for width
        width_layout = QHBoxLayout()
        width_label = QLabel('Width:')
        self.width_input = QLineEdit()
        width_layout.addWidget(width_label)
        width_layout.addWidget(self.width_input)
        layout.addLayout(width_layout)

        # Input for height
        height_layout = QHBoxLayout()
        height_label = QLabel('Height:')
        self.height_input = QLineEdit()
        height_layout.addWidget(height_label)
        height_layout.addWidget(self.height_input)
        layout.addLayout(height_layout)

        # Check box for keeping aspect ratio
        self.aspect_ratio_checkbox = QCheckBox('Keep Aspect Ratio')
        layout.addWidget(self.aspect_ratio_checkbox)

        # Button to select folder containing images
        self.select_folder_button = QPushButton('Select Image Folder')
        self.select_folder_button.clicked.connect(self.select_image_folder)
        layout.addWidget(self.select_folder_button)

        # Resize button
        self.resize_button = QPushButton('Resize Images')
        self.resize_button.clicked.connect(self.resize_images)
        layout.addWidget(self.resize_button)

        self.setLayout(layout)

    def select_image_folder(self):
        folder_path = QFileDialog.getExistingDirectory(
            self, 'Select Image Folder')
        if folder_path:
            self.image_folder = folder_path

    def resize_images(self):
        # Get user inputs for width and height
        try:
            width = int(self.width_input.text())
            height = int(self.height_input.text())
            keep_aspect_ratio = self.aspect_ratio_checkbox.isChecked()
        except ValueError:
            QMessageBox.warning(self, 'Error', 'Please enter valid dimensions.')
            return

        if not hasattr(self, 'image_folder'):
            QMessageBox.warning(self, 'Error', 'Please select an image folder.')
            return

        supported_formats = ('.png', '.jpg', '.jpeg', '.bmp')
        image_files = [os.path.join(self.image_folder, f)
                       for f in os.listdir(self.image_folder)
                       if f.lower().endswith(supported_formats)]

        for image_file in image_files:
            image = cv2.imread(image_file)
            if keep_aspect_ratio:
                h, w = image.shape[:2]
                if w > h:
                    ratio = width / float(w)
                    height = int(h * ratio)
                else:
                    ratio = height / float(h)
                    width = int(w * ratio)
            resized_image = cv2.resize(image, (width, height), interpolation=cv2.INTER_AREA)
            cv2.imwrite(image_file, resized_image)

        QMessageBox.information(self, 'Success', f'Resized {len(image_files)} images.')
        self.close()

def main():
    app = QApplication(sys.argv)
    window = KeypointAnnotationTool()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
