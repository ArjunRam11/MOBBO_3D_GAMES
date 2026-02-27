"""
data_logging.py — Recording control widget for MOBBO.

Session/Pose/Trial folder hierarchy is managed entirely by SessionManager.

Folder layout:
  Mobbo_data/<patient>/session_<ts>/
    Assessment/
      Pose1/
        Board_Data/Board_Poses.json
        CoP_Data/trial1/data_<ip>.csv
        CoP_Data/trial2/data_<ip>.csv
        Foot_Data/trial1/
        Foot_Data/trial2/
      Pose2/...
    Games/
      <game_name>/Pose1/...
"""

import os
from PyQt5.QtWidgets import QPushButton, QSizePolicy, QMessageBox
from PyQt5.QtCore import pyqtSlot, QObject

from user_input import UserInput
from Frame_Process import Frame_Process
from session_manager import get_session_manager


class DataLogging(QObject):
    def __init__(self, button_layout, mobbo):
        super().__init__()

        self.user_input    = UserInput(button_layout)
        self.frame_process = Frame_Process()
        self.mobbo         = mobbo

        self.is_recording     = False
        self._active_cop_path = None
        self._godot_patient_id = None

        self.record_button = QPushButton("Start Recording")
        self.record_button.setFixedSize(150, 50)
        self.record_button.setIconSize(self.record_button.size())
        self.record_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.record_button.setStyleSheet(
            "QPushButton { text-align: left; background-color: grey; color: white; font-size: 14px; }"
        )
        self.record_button.clicked.connect(self.toggle_recording)
        button_layout.addWidget(self.record_button)

    # ── Patient login ─────────────────────────────────────────────────────────

    def set_patient_from_godot(self, hospital_id: str):
        hospital_id = hospital_id.strip()
        if not hospital_id:
            return
        self._godot_patient_id = hospital_id
        get_session_manager().start_session(hospital_id)
        self.user_input.set_name_from_godot(hospital_id)
        print(f"👤 Patient ready: '{hospital_id}' → {get_session_manager().session_path}")

    # ── Assessment recording (button) ─────────────────────────────────────────

    @pyqtSlot()
    def toggle_recording(self):
        if not self.is_recording:
            self._start_assessment_recording()
        else:
            self._stop_assessment_recording()

    def _start_assessment_recording(self):
        try:
            if self._godot_patient_id:
                self.user_input.force_set_name(self._godot_patient_id)

            patient = self.user_input.get_user_name()
            if not patient:
                raise ValueError(
                    "Patient name not set!\n\n"
                    "  • Log in via Godot registry (auto-filled), OR\n"
                    "  • Type a Name/ID and click Submit\n"
                    "Then press Start Recording."
                )

            mgr = get_session_manager()
            if not mgr.session_path:
                mgr.start_session(patient)

            cop_path  = mgr.next_trial("Assessment")
            foot_path = mgr.current_trial_foot_path("Assessment")
            board_dir = mgr.board_data_path("Assessment")
            self._active_cop_path = cop_path

            self.frame_process.set_recording_state(True, session_path=mgr.session_path, enable_video=False)
            self.mobbo.set_recording_state(
                True,
                cop_trial_path=cop_path,
                patient_name=patient,
                board_data_folder=board_dir,
                foot_trial_path=foot_path
            )

            self.is_recording = True
            self.record_button.setText("Stop Recording")
            self.record_button.setStyleSheet(
                "QPushButton { text-align: left; background-color: red; color: white; font-size: 14px; }"
            )
            print(f"▶️  Assessment recording started → {cop_path}")

        except ValueError as e:
            QMessageBox.warning(None, "Recording Error", str(e))
            self.is_recording = False
        except Exception as e:
            QMessageBox.critical(None, "Recording Error", f"Unexpected error:\n{e}")
            self.is_recording = False

    def _stop_assessment_recording(self):
        self.is_recording = False
        self.frame_process.set_recording_state(False)
        self.mobbo.set_recording_state(False, self._active_cop_path or "")
        self.record_button.setText("Start Recording")
        self.record_button.setStyleSheet(
            "QPushButton { text-align: left; background-color: grey; color: white; font-size: 14px; }"
        )
        self._active_cop_path = None
        print("⏹️  Assessment recording stopped")

    # ── Game recording (called from BOSEstimator on Godot command) ────────────

    def start_game_recording(self, game_name: str = "UnknownGame") -> str:
        mgr = get_session_manager()
        if not mgr.session_path:
            print("⚠️  No active session — cannot start game recording")
            return None

        cop_path  = mgr.next_trial("Games", game_name=game_name)
        foot_path = mgr.current_trial_foot_path("Games", game_name=game_name)
        board_dir = mgr.board_data_path("Games", game_name=game_name)

        self.mobbo.set_recording_state(
            True,
            cop_trial_path=cop_path,
            patient_name=mgr.patient_id,
            board_data_folder=board_dir,
            foot_trial_path=foot_path
        )
        print(f"▶️  Game '{game_name}' recording started → {cop_path}")
        return cop_path

    def stop_game_recording(self, cop_path: str = None):
        self.mobbo.set_recording_state(False, cop_path or "")
        print("⏹️  Game recording stopped")