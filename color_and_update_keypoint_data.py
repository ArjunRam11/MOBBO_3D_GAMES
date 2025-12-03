from PyQt5 import QtWidgets,QtGui
from PyQt5.QtGui import QImage, QPixmap,QColor, QPainter
from PyQt5.QtWidgets import QColorDialog, QComboBox, QPushButton
import json
from pyqtgraph.Qt import QtCore








class KeypointDataWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Keypoint Data")
        self.setGeometry(1000, 100, 300, 400)
        self.layout = QtWidgets.QVBoxLayout(self)
        self.keypoint_data_label = QtWidgets.QLabel(self)
        self.layout.addWidget(self.keypoint_data_label)
        self.setStyleSheet("background-color: black; color: white;")
        
    def update_keypoint_data(self, keypoints, keypoint_names):
        keypoint_text = "Keypoint Data:\n"
        for idx, name in enumerate(keypoint_names):
            keypoint_data = keypoints[idx]
            keypoint_text += f"{name}: ({keypoint_data[0]:.2f}, {keypoint_data[1]:.2f}, {keypoint_data[2]:.2f})\n"
        self.keypoint_data_label.setText(keypoint_text)
        self.keypoint_data_label.adjustSize()


class ColorLegendWidget(QtWidgets.QWidget):
    def __init__(self, labels_colors):
        super().__init__()
        self.labels_colors = labels_colors
        self.setFixedSize(150, 100)  # Set the size of the legend box
    def update_colors(self, new_labels_colors):
        self.labels_colors = new_labels_colors  # Update the colors
        self.update()  # Trigger a repaint

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Set initial coordinates for the legend box items
        x, y = 10, 10
        circle_radius = 20  # Radius of the color circle
        
         # Set the desired font size
        font = painter.font()
        font.setPointSize(12)  # Increase this value to make the text bigger
        painter.setFont(font)

        # Draw the legend
        for label, color in self.labels_colors:
            painter.setBrush(QColor(*color))
            painter.setPen(QtCore.Qt.NoPen)
            painter.drawEllipse(x, y, circle_radius, circle_radius)  # Draw color circle
            # painter.setPen(QtCore.Qt.black)
            painter.setPen(QColor(252, 15, 192))
            painter.drawText(x + 30, y + circle_radius, label)  # Draw the text next to the circle
            y += 25  # Move down for the next label
