from PyQt5 import QtWidgets, QtGui
import os
from datetime import datetime
  
class UserInput(QtWidgets.QWidget):
    def __init__(self, layout):
        super().__init__() 
        # self.mobbo_instance = MobboData()
        
        self.user_name = None
        self.session_path = None  # Store the session path
        

        # Label
        self.label = QtWidgets.QLabel("Enter Name/ID:")
        self.label.setStyleSheet("color: white; font-size: 12px;")
        self.label.setFixedSize(150, 30) 
        layout.addWidget(self.label)

        # Input Field
        self.input_field = QtWidgets.QLineEdit()
        self.input_field.setPlaceholderText("Type here...")
        self.input_field.setStyleSheet("""
            background-color: black;
            color: white;
            border: 1px solid white;
            padding: 5px;
        """)
        self.input_field.setFixedSize(150, 30)
        layout.addWidget(self.input_field)

        # Submit Button
        self.submit_button = QtWidgets.QPushButton("Submit")
        self.submit_button.setFixedSize(100, 30)
        self.submit_button.setStyleSheet("""
            QPushButton {
                background-color: black; 
                color: white; 
                border: 2px solid white;
                padding: 5px; 
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: gray; /* Button highlights on hover */
                border-color: white;
            }
            QPushButton:pressed {
                background-color: white; /* Button flashes white on click */
                color: black;
            }
        """)
        self.submit_button.clicked.connect(self.process_data)
        layout.addWidget(self.submit_button)

        # Set global stylesheet
        self.setStyleSheet("QWidget { background-color: black; }")

    def process_data(self):
        """ Process user input, set the user name, and create a session folder. """
        user_input = self.input_field.text().strip()
        # if not user_input:
        #     self.show_popup("Error", "User name cannot be empty!", QtWidgets.QMessageBox.Warning)
        #     return
        
        # Show confirmation dialog before proceeding
        confirm = self.show_popup("Confirmation", f"Proceed with name: {user_input}?", QtWidgets.QMessageBox.Question, True)
        if not confirm:
            return  # If user clicks "Cancel", stop the process

        self.user_name = user_input
        

        self.create_session_folder()


        # Create session folder inside user directory
        

    def create_session_folder(self):
        """ Create session folder in the format session1_date_time inside Mobbo_data/{user}/ """
        base_path = os.path.join(os.getcwd(), "Mobbo_data", self.user_name)
        os.makedirs(base_path, exist_ok=True)

        existing_sessions = [
            folder for folder in os.listdir(base_path) if folder.startswith("session")
        ]
        
        if existing_sessions:
            latest_session = max(existing_sessions, key=lambda x: int(x.split('_')[0][7:]))
            next_session_num = int(latest_session.split('_')[0][7:]) + 1
        else:
            next_session_num = 1  # First session

        date_time_str = datetime.now().strftime("%d%m%Y_%H%M%S")
        session_folder = f"session{next_session_num}_{date_time_str}"
        self.session_path = os.path.join(base_path, session_folder)  # Store session path

        os.makedirs(self.session_path, exist_ok=True)
        
       
    def show_popup(self, title, message, icon, confirmation=False):
        """ Show a popup message. If confirmation=True, returns True/False based on user choice. """
        msg = QtWidgets.QMessageBox()
        msg.setIcon(icon)
        msg.setWindowTitle(title)
        msg.setText(message)
        
        if confirmation:
            msg.setStandardButtons(QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel)
            response = msg.exec_()
            return response == QtWidgets.QMessageBox.Ok
        else:
            msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
            msg.exec_()

    def get_session_path(self):
        """ Get the session path. """
        return self.session_path

    def get_user_name(self):
        return self.user_name
