import sys
import threading
import cv2
import numpy as np
import pyautogui
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QLabel, QSizePolicy
from PyQt5.QtCore import pyqtSlot, Qt,QObject
from PyQt5.QtGui import QIcon
from datetime import datetime
from PyQt5 import QtWidgets,QtGui

class ScreenRecorderApp(QObject):  # Inherit from QObject for signal-slot mechanism
    def __init__(self, button_layout):
        super().__init__()  # Initialize QObject
        self.is_recording = False
        self.recording_thread = None

        # Button to start/stop recording
        self.record_button = QPushButton("Start Recording")
        self.record_button.setIcon(QIcon("D:/mocap_3d_show/images/start-recording-icon.jpg"))
        self.record_button.setFixedSize(200, 50)
        self.record_button.setIconSize(self.record_button.size())
        self.record_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.record_button.setStyleSheet("QPushButton { text-align: left;background-color: grey;color:white }")

        self.record_button.clicked.connect(self.toggle_recording)  # Connect the button
        button_layout.addWidget(self.record_button)

    @pyqtSlot()
    def toggle_recording(self):
        print("Button clicked!")  # Debug message
        if not self.is_recording:
            print("Toggling to Start Recording")  # Debug
            self.is_recording = True
            self.record_button.setText("Stop Recording")
            self.record_button.setStyleSheet("QPushButton { text-align: left; background-color: red; color: white; font-size: 16px; }")
            self.record_button.setIcon(QIcon("D:/mocap_3d_show/images/stop-recording-icon.png"))
            self.start_recording()
        else:
            print("Toggling to Stop Recording")  # Debug
            self.is_recording = False
            self.record_button.setText("Start Recording")
            self.record_button.setStyleSheet("QPushButton { text-align: left; background-color:grey; color: white; font-size: 16px; }")
            self.record_button.setIcon(QIcon("D:/mocap_3d_show/images/start-recording-icon.jpg"))
            self.stop_recording()

    def start_recording(self):
        print("Starting recording...")  # Debug message
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_path = f"output_{timestamp}.avi"
        self.recording_thread = threading.Thread(target=self.record_screen, args=(output_path,))
        self.recording_thread.start()

    def stop_recording(self):
        print("Stopping recording...")  # Debug message
        self.is_recording = False
        if self.recording_thread and self.recording_thread.is_alive():
            self.recording_thread.join()

    def record_screen(self, output_path):
        print("Recording screen...")  # Debug message
        screen_size = pyautogui.size()
        fourcc = cv2.VideoWriter_fourcc(*"XVID")
        fps = 20.0
        out = cv2.VideoWriter(output_path, fourcc, fps, screen_size)

        while self.is_recording:
            try:
                img = pyautogui.screenshot()
                frame = np.array(img)
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                out.write(frame)
            except Exception as e:
                print(f"Error during screen recording: {e}")

        out.release()
        print("Recording stopped and saved to", output_path)
