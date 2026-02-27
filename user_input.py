"""
user_input.py — Patient name input widget.

Session folder creation is now handled entirely by SessionManager.
This widget only handles the UI (label, text field, submit button).
"""

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import QMetaObject, Qt, Q_ARG
from session_manager import get_session_manager


class UserInput(QtWidgets.QWidget):
    def __init__(self, layout):
        super().__init__()

        self.user_name = None

        # ── Label ─────────────────────────────────────────────────────────
        self.label = QtWidgets.QLabel("Enter Name/ID:")
        self.label.setStyleSheet("color: white; font-size: 12px;")
        self.label.setFixedSize(150, 30)
        layout.addWidget(self.label)

        # ── Input Field ───────────────────────────────────────────────────
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

        # ── Submit Button ─────────────────────────────────────────────────
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
            QPushButton:hover  { background-color: gray; border-color: white; }
            QPushButton:pressed { background-color: white; color: black; }
        """)
        self.submit_button.clicked.connect(self.process_data)
        layout.addWidget(self.submit_button)

        self.setStyleSheet("QWidget { background-color: black; }")

    # ─────────────────────────────────────────────────────────────────────────
    # Manual submit (operator types name and clicks Submit)
    # ─────────────────────────────────────────────────────────────────────────
    def process_data(self):
        user_input = self.input_field.text().strip()
        if not user_input:
            return

        confirm = self._show_popup(
            "Confirmation",
            f"Proceed with name: {user_input}?",
            QtWidgets.QMessageBox.Question,
            confirmation=True
        )
        if not confirm:
            return

        self.user_name = user_input

        # Start session via SessionManager (safe — idempotent for same patient)
        mgr = get_session_manager()
        mgr.start_session(user_input)
        print(f"✅ UserInput: session started for '{user_input}' → {mgr.session_path}")

    # ─────────────────────────────────────────────────────────────────────────
    # Called from DataLogging when Godot sends set_patient (auto-fill)
    # ─────────────────────────────────────────────────────────────────────────
    def set_name_from_godot(self, hospital_id: str):
        """Thread-safe: queues a UI update to the main thread."""
        self.user_name = hospital_id.strip()
        QMetaObject.invokeMethod(
            self,
            "_apply_godot_name",
            Qt.QueuedConnection,
            Q_ARG(str, hospital_id.strip())
        )
        print(f"👤 UserInput: name queued from Godot → '{hospital_id}'")

    @QtCore.pyqtSlot(str)
    def _apply_godot_name(self, hospital_id: str):
        """Runs on main thread — updates the visible input field."""
        self.input_field.setText(hospital_id)
        self.input_field.setStyleSheet("""
            background-color: #003300;
            color: #00ff00;
            border: 1px solid #00ff00;
            padding: 5px;
        """)
        print(f"✅ UserInput: UI field set to '{hospital_id}'")

    def force_set_name(self, hospital_id: str):
        """Commit a name programmatically (called just before recording starts)."""
        self.user_name = hospital_id.strip()
        QMetaObject.invokeMethod(
            self,
            "_apply_godot_name",
            Qt.QueuedConnection,
            Q_ARG(str, self.user_name)
        )
        print(f"✅ UserInput: name committed → '{self.user_name}'")

    # ─────────────────────────────────────────────────────────────────────────
    # Accessors
    # ─────────────────────────────────────────────────────────────────────────
    def get_user_name(self) -> str:
        return self.user_name

    # ─────────────────────────────────────────────────────────────────────────
    # Popup helper
    # ─────────────────────────────────────────────────────────────────────────
    def _show_popup(self, title, message, icon, confirmation=False):
        msg = QtWidgets.QMessageBox()
        msg.setIcon(icon)
        msg.setWindowTitle(title)
        msg.setText(message)
        if confirmation:
            msg.setStandardButtons(QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel)
            return msg.exec_() == QtWidgets.QMessageBox.Ok
        else:
            msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
            msg.exec_()