import sys
import os
from base_of_support_lib import *
from sea_library import *


# Get the absolute path of the parent directory (root directory MOCAP_CLEAN)
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))  # Goes one level up from current script
sys.path.append(root_dir)


from PyQt5 import QtWidgets, QtCore,QtGui

import threading
from COP_wifi_data import *
# from cop_wifi_arjun_32bit import*
from board_pose_estimator import *
import numpy as np
import time

import pyrealsense2 as rs
import cv2
 
from PyQt5 import QtWidgets,QtGui
from pyqtgraph.Qt import QtCore
import pyqtgraph.opengl as gl

from noisecancellation import *
from pyqtlibrary import*
# from n_foot_prediction_copy import*
from foot_process import*


from PyQt5.QtGui import QImage, QPixmap,QColor, QPainter
from PyQt5.QtWidgets import QColorDialog, QComboBox, QPushButton
import json
from scipy.spatial import ConvexHull
from video_recording_program import*
from matplotlib.path import Path
from color_and_update_keypoint_data import*
from user_input import UserInput
from data_logging import DataLogging
# from foot_graph_updater import FootGraphUpdater

from foot_recorder import FootDataRecorder



 
# from cop_graph_update import*

rectanglepoint_data = np.zeros((8, 3))
left_heel_vector=np.zeros((1,3))
left_toe_vector=np.zeros((1,3))
right_heel_vector=np.zeros((1,3))
right_toe_vector=np.zeros((1,3))
pose_3d_keypoints=np.zeros((18,3))
angles = np.zeros((8,1))
cop1 = np.zeros((1, 3))
cop2 = np.zeros((1, 3))
gcop1 = np.zeros((1, 3))
ref_translation=np.zeros((3,1))
ref_rotation_matrix=np.zeros((3,1))

relative_rotation_matrix =np.zeros((3,3))
relative_translation =np.zeros((3,1))
# Initialize as lists that can hold the IP addresses or placeholder values
referenceboard = [""]
varboard = [""]

stop_flag_aruco=False
stop_threads=False

process_complete=False

foot_numpy_points = [None, None]
foot_scatter_points = [None, None]


data_lock = threading.Lock()



# Initialize colors dictionary to store selected colors
selected_colors = {
    
    "cop": (255, 255, 255, 255),    # Default white color  
    "gcop": (255, 0, 0, 255),       # Default red color
    "keypoints": (255, 255, 255, 255), # Default white color
    "keypointsline": (255, 0, 0, 255) # Default red color
}

# Function to save the selected colors to a file
def save_colors():
    with open("selected_colors.json", "w") as file:
        json.dump(selected_colors, file)

# Function to load the saved colors
def load_colors():
    global selected_colors
    try:
        with open("selected_colors.json", "r") as file:
            selected_colors = json.load(file)
    except FileNotFoundError:
        save_colors()   






class ArUco3DVisualizer(QtWidgets.QWidget):
    def __init__(self,bos_estimator):
        super().__init__()

        
        self.bos_estimator=bos_estimator 

        self.variable_initilize()
        self.class_initilize()
        self.initialize_ui()
        self.initialize_3d_objects()
         
        self.initialize_timers()
        self.setup_keypoints()
        self.setup_legend()
        self.area_update()

    def area_update(self):
        self.area_label = QtWidgets.QLabel(self)
        self.area_label.setText("Area: 0.0 m²")  # Default text

        self.area_label.setStyleSheet("background-color: rgba(0, 0, 0, 200); color: red; font-size: 16px; padding: 5px;")

        # self.area_label.setStyleSheet("background-color: rgba(255, 255, 255, 200); font-size: 14px; padding: 5px;")
        self.area_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        self.area_label.setGeometry(10, 10, 150, 40)  # Position (x, y), size (width, height)

    def variable_initilize(self):
        self.latest_frame = None  
        self.left_foot_point=None
        self.right_foot_point=None
         
        self.text_label=[]
          
        self.axis_lines = []
        self.axis_labels = []

        
        self.angle_labels = []
        self.pose_lines = []
       
        self.text_labels = []
        self.angle_labels = []

        self.polygon_line_plot=[]
        self.axes_visible = False


        self.cop_and_weight=None   
        self.weight=0
        

        # Define default colors for each item type
        self.default_colors = {
            'cop1': (255, 0, 0, 128),    # Semi-transparent red for cop1
              
            'gcop1': (0, 0, 255, 128)    # Semi-transparent blue for gcop1
        }




        load_colors()

    def class_initilize(self):
        
        self.keypoint_data_window = KeypointDataWindow()
        self.mobbo=MobboData()
        # self.foot_graph_updater=FootGraphUpdater()

        
        # self.bos_estimator = BOSEstimator()
        
        
        

    def initialize_ui(self):
        self.setWindowTitle('MOBBO Visualization')
        self.main_layout = QtWidgets.QHBoxLayout(self)
        self.setLayout(self.main_layout)

        left_layout = QtWidgets.QVBoxLayout()
        self.initialize_buttons(left_layout)
        self.camera_widget = QtWidgets.QLabel()
        self.camera_widget.setFixedSize(320, 340)
        self.camera_widget.setStyleSheet("background-color: black;")
        left_layout.addWidget(self.camera_widget)

        self.main_layout.addLayout(left_layout)

        self.view = gl.GLViewWidget()
        self.view.setGeometry(0, 0, 800, 600)
        self.initial_camera_position = (0, -5, 2)
        self.reset_camera_position()
        self.main_layout.addWidget(self.view)



        from cop_graph_update import CreateShape
        self.cop= CreateShape( selected_colors,self.view )


    def initialize_buttons(self, layout):
        button_layout = QtWidgets.QVBoxLayout()

        self.data_logging_label = QtWidgets.QLabel("Data Logging")
        self.data_logging_label.setStyleSheet("""
            color: white;
            font-size: 14px;
            
        """)
        self.data_logging_label.setFixedSize(150, 30) 
        button_layout.addWidget(self.data_logging_label)

         
 
       
        self.data_logging_class=DataLogging(button_layout,self.mobbo)
       
 


        self.keypoints_checkbox = QtWidgets.QCheckBox("Keypoints")
        self.keypoint_names_checkbox = QtWidgets.QCheckBox("Keypoint Names")
        self.keypoint_data_checkbox = QtWidgets.QCheckBox("Keypoint Data")
        self.keypoint_angle_checkbox = QtWidgets.QCheckBox("Keypoint Angle")

        self.keypoints_checkbox.setChecked(True)
        self.keypoint_names_checkbox.setChecked(False)
        self.keypoint_data_checkbox.setChecked(False)
        self.keypoint_angle_checkbox.setChecked(False)

        button_layout.addWidget(self.keypoints_checkbox)
        button_layout.addWidget(self.keypoint_names_checkbox)
        button_layout.addWidget(self.keypoint_data_checkbox)
        button_layout.addWidget(self.keypoint_angle_checkbox)

        self.reset_button = QtWidgets.QPushButton("Reset View")
        self.reset_button.clicked.connect(self.reset_camera_position)
        button_layout.addWidget(self.reset_button)

        self.restart_button = QtWidgets.QPushButton("Reset Board")
        self.restart_button.clicked.connect(self.restart_process)
        button_layout.addWidget(self.restart_button)

        self.toggle_camera_button = QtWidgets.QPushButton("Camera")
        self.toggle_camera_button.setCheckable(True)
        self.toggle_camera_button.clicked.connect(self.toggle_camera)
        button_layout.addWidget(self.toggle_camera_button)

        self.toggle_axis_button = QtWidgets.QPushButton("Axis")
        self.toggle_axis_button.clicked.connect(self.toggle_axis)
        button_layout.addWidget(self.toggle_axis_button)

        self.color_dropdown = QComboBox(self)
        self.color_dropdown.addItem("Select Item to Color")
        
        self.color_dropdown.addItem("Cop")
         
        self.color_dropdown.addItem("GCop")
        self.color_dropdown.addItem("Keypoints")
        self.color_dropdown.addItem("KeypointsLine")
        button_layout.addWidget(self.color_dropdown)

        self.color_picker_button = QPushButton("Select Color", self)
        self.color_picker_button.clicked.connect(self.open_color_picker)
        button_layout.addWidget(self.color_picker_button)

        layout.addLayout(button_layout)

        self.setStyleSheet("""
            QWidget { background-color: black; }
            QPushButton { background-color: black; color: white; border: 2px solid white; padding: 5px; font-size: 14px; }
            QPushButton:hover {background-color: #222222; border-color: #888888;}                    
            QPushButton:pressed {background-color: #444444;border-color: #bbbbbb;}       
            QPushButton:checked { background-color: white; color: black; }
            QCheckBox { color: white; }
            QComboBox { background-color: black; color: white; border: 2px solid white; }
            QComboBox QAbstractItemView { background-color: black; color: white; border: 1px solid white; }
        """)
        
 
        
 

        

    def initialize_3d_objects(self):
        self.grid = gl.GLGridItem()
        self.grid.scale(1, 1, 1)
        self.view.addItem(self.grid)

        self.create_text_item_center(name="(0, 0, 0)", position=np.array([0, 0, 0]))

        self.axis_lines = []
        self.text_label = []
        self.axes_visible = False

        
        self.gcop1_mesh = gl.GLMeshItem()

         

         
        self.gcop__1 = gl.GLScatterPlotItem()
        self.view.addItem(self.gcop__1)
        self.view.addItem(self.gcop1_mesh)

        self.keypoints_3d = gl.GLScatterPlotItem()
        self.view.addItem(self.keypoints_3d)

        self.left_foot_mesh = gl.GLMeshItem()
        self.right_foot_mesh = gl.GLMeshItem()
        self.view.addItem(self.left_foot_mesh)
        self.view.addItem(self.right_foot_mesh)

        self.right_scatter = gl.GLScatterPlotItem()
        self.left_scatter = gl.GLScatterPlotItem()
        self.view.addItem(self.right_scatter)
        self.view.addItem(self.left_scatter)

    

    def initialize_timers(self):
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_plot)
        self.timer.timeout.connect(self.update_text_size)
        self.timer.timeout.connect(self.foot_graph_update)
         
        self.timer.timeout.connect(self.update_color_legend)
        self.timer.start(50)

       

    def setup_keypoints(self):
        self.keypoints = {
            'H': 0, 'N': 1, 'RS': 2, 'LS': 3,
            'RE': 4, 'LE': 5, 'RH': 6, 'LH': 7,
            'R_Hip': 8, 'L_hip': 9, 'R_k': 10, 'L_k': 11,
            'RF': 12, 'LF': 13, 'L_H': 14, 'R_H': 15, 'L_F_I': 16, 'R_F_I': 17
        }

        self.POSE_CONNECTIONS = [
            (0, 1), (1, 2), (0, 3), (1, 3), (2, 4), (4, 6), (3, 5), (3, 9),
            (5, 7), (2, 8), (8, 10), (10, 12), (9, 11), (11, 13), (9, 8), (14, 16), (13, 14), (15, 17), (12, 15), (13, 16), (12, 17)
        ]

        self.angle_indices = {
            'RE': 4, 'LE': 5, 'RS': 2, 'LS': 3, 'R_k': 10, 'L_k': 11, 'RF': 12, 'LF': 13
        }



    # The graph visualization of COP   color managing

    def setup_legend(self):
        cop1_color_rgba = selected_colors.get('cop', (255, 255, 255, 255))
        
        gcop_color_rgba = selected_colors.get('gcop', (255, 0, 0, 255))

        cop1_color_rgb = tuple(cop1_color_rgba[i] for i in range(3))
        
        gcop_color_rgb = tuple(gcop_color_rgba[i] for i in range(3))

        labels_colors = [
            ("Cop", cop1_color_rgb),
             
            ("GCop", gcop_color_rgb)
        ]

        self.legend_widget = ColorLegendWidget(labels_colors)
        self.legend_widget.setStyleSheet("background-color: rgba(255, 255, 255, 200);")
        self.legend_widget.setParent(self)
        self.legend_widget.setGeometry(self.view.width() - 180, 10, 150, 100)
        self.legend_widget.raise_()

    def update_color_legend(self):
        cop1_color_rgba = selected_colors.get('cop', (255, 255, 255, 255))
         
        gcop_color_rgba = selected_colors.get('gcop', (255, 0, 0, 255))

        cop1_color_rgb = tuple(cop1_color_rgba[i] for i in range(3))
         
        gcop_color_rgb = tuple(gcop_color_rgba[i] for i in range(3))

        labels_colors = [
            ("Cop", cop1_color_rgb),
             
            ("GCop", gcop_color_rgb)
        ]

        self.legend_widget.update_colors(labels_colors)

     
    def open_color_picker(self):
        """
        Opens a color picker dialog and allows the user to select a color with transparency (RGBA).
        """
        color_dialog = QColorDialog()
        color_dialog.setOption(QColorDialog.ShowAlphaChannel, True)  # Enable transparency
        selected_color = color_dialog.getColor()
        if selected_color.isValid():
            color_tuple = (
                selected_color.red(),
                selected_color.green(),
                selected_color.blue(),
                selected_color.alpha()  # Include the alpha value
            )
            selected_item = self.color_dropdown.currentText().lower()
            if selected_item in selected_colors:
                selected_colors[selected_item] = color_tuple
                save_colors()  # Save the selected color
                print(f"Selected color for {selected_item}: {color_tuple}")

        
    
 

    # The axis of update graph
    def toggle_axis(self):
        """Toggle the visibility of X, Y, and Z axes."""
        if self.axes_visible:
            self.remove_axes()
        else:
            self.add_axes()

    def add_axes(self):
        """Add X, Y, and Z axes lines and labels to the 3D view."""
        if not self.axes_visible:
           
            length = 0.5
 
            x_axis = np.array([[0, 0, 0], [length, 0, 0]])
            x_line = self.add_axis_line(x_axis, color= (1.0, 0, 0, 1))  # Red
            self.axis_lines.append(x_line)
 
            y_axis = np.array([[0, 0, 0], [0, length, 0]])
            y_line = self.add_axis_line(y_axis,  color=(0, 1.0, 0, 1))  # Green
            self.axis_lines.append(y_line)
 
            z_axis = np.array([[0, 0, 0], [0, 0, length]])
            z_line = self.add_axis_line(z_axis, color=(0, 0, 1.0, 1))  # Blue
            self.axis_lines.append(z_line)
 
            self.create_text_item_axis(name="X", position=np.array([length, 0, 0]))  # X Label
            self.create_text_item_axis(name="Y", position=np.array([0, length, 0]))  # Y Label
            self.create_text_item_axis(name="Z", position=np.array([0, 0, length]))  # Z Label

            self.axes_visible = True

    def remove_axes(self):
        """Remove X, Y, and Z axes lines and labels from the 3D view."""
        if  self.axes_visible:
             
            for line in self.axis_lines:
                self.view.removeItem(line)
            self.axis_lines.clear()
 
            for label in self.text_label:
                self.view.removeItem(label)
            self.text_label.clear()

            self.axes_visible = False


    def add_axis_line(self, points, color):
        """Add an axis line to the 3D view."""
        line_item = gl.GLLinePlotItem(pos=points, color=color, width=2, antialias=True)
        self.view.addItem(line_item)
        return line_item

    def create_text_item_axis(self, name, position):
        """Create a text label at the given 3D position."""
        text_item = gl.GLTextItem(text=name, pos=position, font=QtGui.QFont('Helvetica', 16))
        self.view.addItem(text_item)
        self.text_label.append(text_item)



    # show the center point of text||

    def create_text_item_center(self, name, position):
        # Create a text item with an initial font size
        font_size = self.get_dynamic_font_size()
        text_item = gl.GLTextItem(pos=position, text=name, font=QtGui.QFont('Helvetica', font_size))
        self.view.addItem(text_item)
        self.text_label.append(text_item)

    def get_dynamic_font_size(self):
        # Calculate font size based on the camera's distance from the scene center
        cam_pos = self.view.cameraPosition()   
        distance = np.linalg.norm([cam_pos.x(), cam_pos.y(), cam_pos.z()])  
        base_font_size = 3       
        scaled_font_size = int(base_font_size / (distance * 0.1))
        return max(scaled_font_size, 5)  

    def update_text_size(self):
        # Dynamically update the font size of all text items
        for text_item in self.text_label:
            new_font_size = self.get_dynamic_font_size()            
            text_item.text = text_item.text  
            text_item.font = QtGui.QFont('Helvetica', new_font_size)   



    # camer switch process
    
    def toggle_camera(self):
        if self.camera_widget.isVisible():
            self.camera_widget.hide()
            self.toggle_camera_button.setText("Show Camera View")
        else:
            self.camera_widget.show()
            self.toggle_camera_button.setText("Hide Camera View")

    def restart_process(self):
        """Handle the button click to stop and restart threads."""
        print("Restart button clicked!")   
        self.bos_estimator.stop_all_threads()  
        time.sleep(1)   
        self.bos_estimator.reset_all_threads()  
        print("Threads restarted!")  

    def reset_camera_position(self):
        eye_x, eye_y, eye_z = self.initial_camera_position

        distance = np.sqrt(eye_x ** 2 + eye_y ** 2 + eye_z ** 2)
        elevation = np.degrees(np.arctan2(eye_z, np.sqrt(eye_x ** 2 + eye_y ** 2)))
        azimuth = np.degrees(np.arctan2(eye_y, eye_x))

        self.view.setCameraPosition(distance=distance, elevation=elevation, azimuth=azimuth)

    def resizeEvent(self, event):
        """Ensure the legend stays at the top-right corner when resizing the window."""
        # Get the width of the entire widget, not just the view
        widget_width = self.width()
        
        # Set the geometry of the legend widget relative to the whole widget
        self.legend_widget.setGeometry(widget_width - 180, 10, 150, 100)
        
        super().resizeEvent(event)

    def update_plot(self):
        global process_complete

        # if process_complete:
        
        with data_lock:

                 
                if self.keypoints_checkbox.isChecked() and np.any(pose_3d_keypoints) and  not np.isnan(pose_3d_keypoints).all():
                    self.update_pose_keypoints(pose_3d_keypoints)
                    if self.keypoint_angle_checkbox.isChecked() and np.any(angles) and angles is not None:
                        self.update_angle_labels(angles,pose_3d_keypoints)
                    else:
                        for label in self.angle_labels:
                            self.view.removeItem(label)
                        self.angle_labels.clear()
                    if self.keypoint_names_checkbox.isChecked():
                        self.update_keypoint_labels(pose_3d_keypoints)
                    else:
                        self.clear_text_labels()
                else:
                    self.keypoints_3d.setData(pos=np.array([[0, 0, 0]]))
                    for line_item in self.pose_lines:
                        self.view.removeItem(line_item)
                    self.pose_lines.clear()
                    self.clear_text_labels()
                if self.keypoint_data_checkbox.isChecked():
                    self.keypoint_data_window.update_keypoint_data(pose_3d_keypoints, list(self.keypoints.keys()))
                    self.keypoint_data_window.show()
                else:
                    self.keypoint_data_window.hide()

                if gcop1 is not None:

                    
                    self.cop.gcop_update ( self.gcop1_mesh, gcop1,self.weight )



        if self.cop_and_weight is not None:

            self.cop.update_all_cops(self.cop_and_weight)
             

             
                
              
               

    
    def cop_and_gcop_update(self,cop_and_weight,weight ):


        self.cop_and_weight=cop_and_weight
         
        self.weight=weight

        

         
    def camera_update(self, latest_frame):
        

        if  latest_frame is not None:   
            self.display_camera_feed(  latest_frame)


    def display_camera_feed(self, image):
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        scaled_image = cv2.resize(rgb_image, (320, 340)) #, interpolation=cv2.INTER_LINEAR)
        h, w, ch = scaled_image.shape
        bytes_per_line = ch * w
        qt_image = QtGui.QImage(scaled_image.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)
        pixmap = QtGui.QPixmap.fromImage(qt_image)
        self.camera_widget.setPixmap(pixmap)


    def update_angle_labels(self, angles, keypoints):
        """ Update the text labels for angles at specific keypoints. """
        for label in self.angle_labels:
            self.view.removeItem(label)
        self.angle_labels.clear()
        angles=angles
        keypoints=keypoints
        for angle_key, index in self.angle_indices.items():
            angle =  angles[list(self.angle_indices.keys()).index(angle_key)][0] # Extract the scalar value
            x, y, z = keypoints[index]
            angle_label = gl.GLTextItem(text=f"{angle:.2f}°",  pos=(x,y,z))  # Yellow color
            self.view.addItem(angle_label)
            self.angle_labels.append(angle_label)

     
   

    def update_keypoint_labels(self, keypoints):
        self.clear_text_labels()  # Clear existing labels
        for name, index in self.keypoints.items():
            if index < len(keypoints) and not np.isnan(keypoints[index]).any():
                position = keypoints[index]
                text_item = gl.GLTextItem(text=name, pos=position)  # White color for labels
                self.view.addItem(text_item)
                self.text_labels.append(text_item)

    def clear_text_labels(self):
        for label in self.text_labels:
            self.view.removeItem(label)
        self.text_labels.clear()

    def update_pose_keypoints(self, keypoints):
        if np.any(keypoints):
            pos = keypoints
            self.keypoints_3d.setData(pos=pos, size=10, color=(1, 1, 1, 1))  # White color for keypoints
            self.update_pose_connections(keypoints)

    def update_pose_connections(self, keypoints):
        for line_item in self.pose_lines:
            self.view.removeItem(line_item)
        self.pose_lines.clear()
        self.clear_text_labels()  # Clear existing text labels
        for start, end in self.POSE_CONNECTIONS:
            if (start < len(keypoints) and end < len(keypoints) and
                    not np.isnan(keypoints[start]).any() and not np.isnan(keypoints[end]).any()):
                pts = np.vstack([keypoints[start], keypoints[end]])
                selected_color = selected_colors.get('keypointsline', (255, 0, 0, 255))  # Default to opaque red
                rgba_color = tuple(c / 255.0 for c in selected_color)  # Normalize color values to 0-1 range
                line_item = gl.GLLinePlotItem(pos=pts, color=rgba_color, width=15)  # Use the normalized color
                self.view.addItem(line_item)  # Add the line item to the view
                self.pose_lines.append(line_item)  # Append to pose_lines list


    def foot_graph_update(self):


        # self.foot_graph_updater=FootGraphUpdater(self.bos_estimator,self.view,self.right_foot_mesh,self.left_foot_mesh,self.right_scatter,self.left_scatter,self.area_label)


        self.right_foot_mesh.setMeshData(vertices=np.array([[0, 0, 0]]), faces=np.array([[0, 0, 0]]))  # Clear right foot mesh
        self.left_foot_mesh.setMeshData(vertices=np.array([[0, 0, 0]]), faces=np.array([[0, 0, 0]]))  # Clear left foot mesh
        self.right_scatter.setData(pos=np.empty((0, 3)))  # Explicitly clear scatter with empty 3D points
        self.left_scatter.setData(pos=np.empty((0, 3)))  # Same for left scatter
        self.area_label.setText("Area: 0.0 m²")  # Default text
        for lines in self.polygon_line_plot:
            self.view.removeItem(lines)
        self.polygon_line_plot.clear()

        foot_numpy_points=self.bos_estimator.foot_numpy_points
        foot_scatter_points=self.bos_estimator.foot_scatter_points

        # print("foot numpy===",   foot_numpy_points)

        # print('foot scatter points===',  foot_scatter_points)
 
        
        detect_id = -1
        gcop1_current=gcop1

        # print( foot_scatter_points)

        if foot_numpy_points is not None :
            

            
            for idx, foot in enumerate(foot_numpy_points):

                if foot is not None:
                    foot_2d = foot[:, :2]  # Take only x and y coordinates (ignoring z)
                    _poly = Path(foot_2d)
                    if gcop1_current is not None:
                        # if _poly.contains_point(gcop1_current.reshape(-1)[:2]):
                        if _poly.contains_point(gcop1_current.reshape(-1)[:2]):
                            # print("foot_numpy is visual:  ", foot_numpy_points)
                            detect_id = idx                     
                            foot = foot_numpy_points[detect_id]
                            scatter = foot_scatter_points[detect_id]
                            if detect_id == 0:  # Right foot
                                # print("right foot")
                                self.update_mesh_foot_plot(self.right_foot_mesh, foot)
                                self.update_scatter(self.right_scatter, [scatter[0], scatter[1]])
                                self.hull_shape_find_and_draw( foot)
                            elif detect_id == 1:  # Left foot
                                # print("left foot")
                                self.update_mesh_foot_plot(self.left_foot_mesh, foot)
                                self.update_scatter(self.left_scatter, [scatter[0], scatter[1]])
                                self.hull_shape_find_and_draw(foot)
                            return
                    
            if foot_numpy_points[0] is not None:
                    self.update_mesh_foot_plot(self.right_foot_mesh, foot_numpy_points[0])
            else:                
                self.clear_mesh(self.right_foot_mesh)

            if foot_scatter_points[0] is not None:
                self.update_scatter(
                    self.right_scatter, [foot_scatter_points[0][0], foot_scatter_points[0][1]]
                )
            else:
                self.right_scatter.setData(pos=np.empty((0, 3)))  # Explicitly clear scatter with empty 3D points

            if foot_numpy_points[1] is not None:
                self.update_mesh_foot_plot(self.left_foot_mesh, foot_numpy_points[1])
            else:  
                self.clear_mesh(self.left_foot_mesh)

            if foot_scatter_points[1] is not None:
                self.update_scatter(
                    self.left_scatter, [foot_scatter_points[1][0], foot_scatter_points[1][1]]
                )
            else:
                self.left_scatter.setData(pos=np.empty((0, 3)))  # Same for left scatter

            if self.bos_estimator.left_foot_polygon_point is not None and self.bos_estimator.right_foot_polygon_point is not None:
                combined_points = np.vstack([self.bos_estimator.left_foot_polygon_point,self.bos_estimator.right_foot_polygon_point])
                self.hull_shape_find_and_draw(combined_points)
            else:
                for lines in self.polygon_line_plot:
                    self.view.removeItem(lines)
                self.polygon_line_plot.clear()

    def clear_mesh(self, mesh_item):
        """Clear the mesh by setting it to an empty state."""
        mesh_item.setMeshData(vertices=np.array([[0, 0, 0]]), faces=np.array([[0, 0, 0]]))  # Clear mesh data
        mesh_item.setVisible(False) 

    def update_scatter(self, scatter_item, points):
        """
        Update scatter plot points for heel and toe visualization.
        """
        scatter_item.setData(pos=np.array(points), size=10, color=(1, 0, 0, 1))

    def update_mesh_foot_plot(self,mesh_item,foot_points):

       
        import numpy as np
        from scipy.spatial import ConvexHull, Delaunay
        import pyqtgraph.opengl as gl
        from itertools import combinations

        if foot_points is None:
            print("foot_points is None")  # Debug: None check
            mesh_item.setMeshData(vertexes=np.array([]), faces=np.array([]))
            return
        delaunay = Delaunay(foot_points[:, :2])
        faces = delaunay.simplices
        colors = np.array([[0.878, 0.675, 0.412, 1]] * len(faces))
        meshdata = gl.MeshData(vertexes=foot_points, faces=faces, faceColors=colors)
        mesh_item.setMeshData(meshdata=meshdata, smooth=False, computeNormals=False)
        mesh_item.setVisible(True)

    def area_polygon(self, combined_points):


        projected_points = combined_points[:, :2]
        hull = ConvexHull(projected_points)
        hull_vertices = projected_points[hull.vertices]
        polygon_area = 0.5 * np.abs(
            np.dot(hull_vertices[:, 0], np.roll(hull_vertices[:, 1], 1)) -
            np.dot(hull_vertices[:, 1], np.roll(hull_vertices[:, 0], 1))
        )
        self.area_label.setText(f"Area : {polygon_area:.5f} m²")
        # print("Polygon Area (2D):", polygon_area)

    def hull_shape_find_and_draw (self,combined_points):


        self.area_polygon(combined_points)
        jogging = np.random.uniform(-1e-6, 1e-6, size=(combined_points.shape[0], 1))
        adjusted_points = combined_points + np.hstack([np.zeros((combined_points.shape[0], 2)), jogging])
        hull = ConvexHull(adjusted_points)
        for lines in self.polygon_line_plot:
            self.view.removeItem(lines)
        self.polygon_line_plot.clear()
        hull_points = hull.points [ hull.vertices]
        closed_hull_points = np.vstack([hull_points, hull_points[0]])
        line_item = gl.GLLinePlotItem(pos=closed_hull_points, color=(0.25, 0.88, 0.82, 1), width=6, mode='line_strip')
        self.view.addItem(line_item)
        self.polygon_line_plot.append(line_item)
    




 