import sys
import threading
import cv2
import numpy as np
import pyautogui
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QLabel, QSizePolicy,QMessageBox
from PyQt5.QtCore import pyqtSlot, Qt,QObject
from PyQt5.QtGui import QIcon
from datetime import datetime
from PyQt5 import QtWidgets,QtGui
import os
from user_input import UserInput
from Frame_Process import Frame_Process
 

 


class DataLogging(QObject):  # Inherit from QObject for signal-slot mechanism
    def __init__(self, button_layout,mobbo):
        super().__init__()  # Initialize QObject
         
        self.user_input=UserInput(button_layout)
        self.frame_process=Frame_Process()
        
        self.mobbo=mobbo
        self.is_recording = False
        self.recording_thread = None
        self.trail_data_path=None
        
        

        # Button to start/stop recording
        self.record_button = QPushButton("Start Recording")
        # self.record_button.setIcon(QIcon("D:/mocap_3d_show/images/start-recording-icon.jpg"))
        self.record_button.setFixedSize(150, 50)
        self.record_button.setIconSize(self.record_button.size())
        self.record_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.record_button.setStyleSheet("QPushButton { text-align: left;background-color: grey;color:white }")

        self.record_button.clicked.connect(self.toggle_recording)  # Connect the button
        button_layout.addWidget(self.record_button)

    @pyqtSlot()
    def toggle_recording(self):
        
        if not self.is_recording:
            
            self.is_recording = True
            self.start_recording()
            self.trail_data_path=self.create_trial_folder()
            
            self.frame_process.set_recording_state(self.is_recording,self.trail_data_path)
            
            self.mobbo.set_recording_state( self.is_recording,self.trail_data_path)
            self.record_button.setText("Stop Recording")
            self.record_button.setStyleSheet("QPushButton { text-align: left; background-color: red; color: white; font-size: 16px; }")
            self.record_button.setIcon(QIcon("D:/mocap_3d_show/images/stop-recording-icon.png"))
            
           
        else:
            
            self.is_recording = False
            self.stop_recording()
            self.frame_process.set_recording_state(self.is_recording,self.trail_data_path)
            self.mobbo.set_recording_state( self.is_recording,self.trail_data_path)
            self.record_button.setText("Start Recording")
            self.record_button.setStyleSheet("QPushButton { text-align: left; background-color:grey; color: white; font-size: 16px; }")
            self.record_button.setIcon(QIcon("D:/mocap_3d_show/images/start-recording-icon.jpg"))
           


    def start_recording(self):
            
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            self.set_user_name()

            
         

    def stop_recording(self):
         
        self.is_recording = False

    def set_user_name(self ):
        name=self.user_input.get_user_name()

        
        self.user_name = name.strip()
        self.session_path = self.user_input.get_session_path()
        self.trial_number = self.get_next_trial_number()  # Initialize trial number
        
         

     

    def get_next_trial_number(self):
        """Determine the next available trial number."""
        if not  self.session_path:  # Ensure session path is not None
            raise ValueError("Error: Session path is not set. Call set_user_name() first.")

        if not os.path.exists( self.session_path):
            os.makedirs( self.session_path)

        existing_trials = [
            int(folder[5:6]) for folder in os.listdir( self.session_path) if folder.startswith("trial")
        ]

        return max(existing_trials, default=0) + 1  # Return next available trial number

    def create_trial_folder(self):
        """Create a new trial folder inside the current session."""
        if not self.user_name or not  self.session_path:
            raise ValueError("Error: User session is not initialized. Call set_user_name() first.")

        trial_number = self.get_next_trial_number()
        date_time_str = datetime.now().strftime("%d%m%Y_%H%M%S")
        trial_folder = os.path.join( self.session_path, f"trial{ trial_number}_{date_time_str}")

        if not os.path.exists(trial_folder):
            os.makedirs(trial_folder)

         
         
        return trial_folder  # Return path of the created trial folder
 
         


 


 

