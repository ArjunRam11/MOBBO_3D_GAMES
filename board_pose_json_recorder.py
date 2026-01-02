"""
Board Pose JSON Recorder - Saves board pose data with layout information to JSON format.

Accumulates multiple board poses in a single JSON file (one per reset/recording session).
Implements proper patient/session folder hierarchy:

Mobbo_data/
└── [PATIENT_NAME]/
    └── [SESSION_FOLDER_trial_TIMESTAMP]/
        ├── Board_Data/
        │   └── Board_Poses.json (with layout + CSV file paths)
        ├── CoP_Data/
        │   └── cop_data_[timestamp].csv (new one per recording start)
        └── Foot_Data/
            └── foot_data_[timestamp].csv (new one per recording start)

Format:
{
    "metadata": {
        "patient_name": "arjn",
        "session_folder": "session_20251224_145606",
        "created_at": "2025-12-24T14:37:44.650",
        "total_poses": 2
    },
    "board_layout": {
        "num_boards": 2,
        "layout": "1x2",
        "rows": 1,
        "cols": 2,
        "arrangement_type": "left_right",
        "spacing": {"x_spacing": 61.69, "y_spacing": 4.73},
        ...
    },
    "poses": [
        {
            "timestamp": "2025-12-24T14:37:44.650",
            "board_data": [...],
            "data_files": {
                "cop_data": "CoP_Data/cop_data_20251224_145608.csv",
                "foot_data": "Foot_Data/foot_data_20251224_145608.csv"
            }
        },
        {
            "timestamp": "2025-12-24T14:37:50.123",
            "board_data": [...],
            "data_files": {...}
        }
    ]
}
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
import numpy as np

logger = logging.getLogger(__name__)


class BoardPoseJSONRecorder:
    """Handles recording board pose data to JSON with layout information and file path references."""

    def __init__(self, patient_name: str, trial_path: str):
        """
        Initialize JSON recorder for a patient/session.

        Args:
            patient_name: Name of the patient (used for folder organization)
            trial_path: Path to trial folder or session folder
        """
        self.patient_name = patient_name
        self.trial_path = trial_path

        # Extract or create session folder path
        self.session_folder = self._create_session_folder(patient_name, trial_path)

        # Create Board_Data folder inside session
        self.board_data_dir = os.path.join(self.session_folder, "Board_Data")
        os.makedirs(self.board_data_dir, exist_ok=True)
        logger.info(f"✅ Board_Data folder created: {self.board_data_dir}")
        print(f"✅ Board_Data folder created: {self.board_data_dir}")

        # Create CoP_Data and Foot_Data folders for CSV files
        self.cop_data_dir = os.path.join(self.session_folder, "CoP_Data")
        self.foot_data_dir = os.path.join(self.session_folder, "Foot_Data")
        os.makedirs(self.cop_data_dir, exist_ok=True)
        logger.info(f"✅ CoP_Data folder created: {self.cop_data_dir}")
        print(f"✅ CoP_Data folder created: {self.cop_data_dir}")

        os.makedirs(self.foot_data_dir, exist_ok=True)
        logger.info(f"✅ Foot_Data folder created: {self.foot_data_dir}")
        print(f"✅ Foot_Data folder created: {self.foot_data_dir}")

        # JSON file path (fixed name per session)
        self.json_filename = os.path.join(self.board_data_dir, "Board_Poses.json")
        logger.info(f"✅ JSON file path set: {self.json_filename}")
        print(f"✅ JSON file path set: {self.json_filename}")

        # Board layout data and poses
        self.board_layout_data = None
        self.poses = []

        # Load existing poses if JSON already exists (for persistence across resets)
        self._load_existing_poses()

        logger.info(f"📊 BoardPoseJSONRecorder initialized for patient '{patient_name}'")
        logger.info(f"   Session folder: {self.session_folder}")
        print(f"📊 BoardPoseJSONRecorder initialized for patient '{patient_name}'")
        print(f"   Session folder: {self.session_folder}")

    def _create_session_folder(self, patient_name: str, trial_path: str) -> str:
        """
        Create or get session folder path with proper patient/session structure.

        Args:
            patient_name: Name of the patient
            trial_path: Full path to session folder (already created by main.py with timestamp)

        Returns:
            Path to session folder
        """
        logger.info(f"📍 _create_session_folder called:")
        logger.info(f"   patient_name: {patient_name}")
        logger.info(f"   trial_path: {trial_path}")

        # FIXED: USE the trial_path that's already been created by main.py
        # The trial_path is in format: Mobbo_data/[PATIENT_NAME]/session_[TIMESTAMP]/
        # It already exists and has the correct folder structure
        if trial_path and os.path.isabs(trial_path):
            # trial_path is already an absolute path created by main.py
            session_folder = trial_path
            logger.info(f"✅ Using trial_path provided by main.py: {session_folder}")
        elif trial_path and trial_path.strip():
            # trial_path might be relative or partial - make it absolute
            # Try to construct it assuming it's in the script directory
            script_dir = os.path.dirname(os.path.abspath(__file__))
            session_folder = os.path.join(script_dir, trial_path)
            logger.info(f"✅ Constructed session folder path: {session_folder}")
        else:
            # Fallback: create new session folder (for backwards compatibility)
            logger.warning(f"⚠️ No trial_path provided - creating new session folder")
            script_dir = os.path.dirname(os.path.abspath(__file__))
            base_path = os.path.join(script_dir, "Mobbo_data")
            patient_dir = os.path.join(base_path, patient_name)
            timestamp = datetime.now().strftime("%d%m%Y_%H%M%S")
            session_name = f"session_{timestamp}"
            session_folder = os.path.join(patient_dir, session_name)

        # Ensure folder exists (it should already exist from main.py, but create just in case)
        os.makedirs(session_folder, exist_ok=True)
        logger.info(f"✅ Session folder ready: {session_folder}")

        return session_folder

    def _load_existing_poses(self):
        """Load existing poses from JSON if file exists (for persistence)."""
        try:
            if os.path.exists(self.json_filename):
                with open(self.json_filename, 'r') as f:
                    data = json.load(f)
                    self.poses = data.get('poses', [])
                    if 'board_layout' in data:
                        self.board_layout_data = data['board_layout']
                    logger.info(f"✅ Loaded {len(self.poses)} existing poses from {self.json_filename}")
        except Exception as e:
            logger.warning(f"⚠️ Could not load existing poses: {e}")

    def set_board_layout(self, layout_data: Dict[str, Any]):
        """
        Store board layout information to be included in the JSON.

        Args:
            layout_data: Dict from analyze_board_layout() containing layout info
        """
        self.board_layout_data = layout_data
        logger.info(f"📐 Board layout set: {layout_data.get('layout', 'unknown')}")

    def record_board_pose(self, board_position_list: List[Dict],
                         cop_csv_path: Optional[str] = None,
                         foot_csv_path: Optional[str] = None) -> str:
        """
        Record a board pose and save/update JSON file.

        This is called on each recording start (and subsequent resets).
        Accumulates poses in the same JSON file for the entire session.
        On reset, appends new pose to existing JSON instead of overwriting.

        Args:
            board_position_list: List of board data dicts, each containing:
                - board_translation: [x, y, z] position
                - ip_address: Board's IP address
                - angle: Rotation angle
                - rotation_matrix: 3x3 rotation matrix
                - board_aruco_ids: List of detected ArUco IDs
            cop_csv_path: Optional relative path to CoP data CSV file
            foot_csv_path: Optional relative path to foot data CSV file

        Returns:
            str: Path to the saved JSON file
        """
        try:
            logger.debug(f"🔍 record_board_pose() called with {len(board_position_list) if board_position_list else 0} boards")
            print(f"🔍 record_board_pose() called with {len(board_position_list) if board_position_list else 0} boards")
            print(f"   Session folder: {self.session_folder}")
            print(f"   JSON file: {self.json_filename}")

            # Create a new pose entry
            pose_entry = {
                "timestamp": datetime.now().isoformat(),
                "board_data": self._format_board_data(board_position_list),
                "data_files": {}
            }

            # Add file path references if provided
            if cop_csv_path:
                pose_entry["data_files"]["cop_data"] = cop_csv_path
            if foot_csv_path:
                pose_entry["data_files"]["foot_data"] = foot_csv_path

            # Add pose to accumulator
            self.poses.append(pose_entry)

            # Build complete JSON structure with metadata
            json_data = {
                "metadata": {
                    "patient_name": self.patient_name,
                    "session_folder": os.path.basename(self.session_folder),
                    "created_at": datetime.now().isoformat(),
                    "total_poses": len(self.poses)
                },
                "poses": self.poses
            }

            # Include board layout if available
            if self.board_layout_data:
                json_data["board_layout"] = self.board_layout_data

            # Write JSON file atomically
            print(f"🔍 About to write JSON file: {self.json_filename}")
            self._write_json_atomic(self.json_filename, json_data)
            print(f"✅ JSON file written successfully: {self.json_filename}")

            num_boards = len(board_position_list) if board_position_list else 0
            logger.info(
                f"💾 Board pose {len(self.poses)} saved to JSON "
                f"({num_boards} boards recorded)"
            )
            print(
                f"💾 Board pose {len(self.poses)} saved to JSON "
                f"({num_boards} boards recorded)"
            )
            if cop_csv_path:
                logger.info(f"   CoP data: {cop_csv_path}")
                print(f"   CoP data: {cop_csv_path}")
            if foot_csv_path:
                logger.info(f"   Foot data: {foot_csv_path}")
                print(f"   Foot data: {foot_csv_path}")

            return self.json_filename

        except Exception as e:
            logger.error(f"❌ Failed to record board pose to JSON: {e}", exc_info=True)
            print(f"❌ Failed to record board pose to JSON: {e}")
            import traceback
            traceback.print_exc()
            raise

    def _format_board_data(self, board_position_list: List[Dict]) -> List[Dict]:
        """
        Format board data for JSON serialization (convert numpy arrays to lists).

        Args:
            board_position_list: Raw board data from COP_wifi_data

        Returns:
            List of formatted board data dicts
        """
        formatted_boards = []

        for data in board_position_list:
            formatted_data = {
                "board_translation": self._to_list(data.get("board_translation")),
                "ip_address": str(data.get("ip_address", "")).strip(),
                "angle": self._to_list(data.get("angle")),
                "rotation_matrix": self._to_list(data.get("rotation_matrix")),
                "board_aruco_ids": self._to_list(data.get("board_aruco_ids"))
            }
            formatted_boards.append(formatted_data)

        return formatted_boards

    @staticmethod
    def _to_list(value: Any) -> Any:
        """Convert numpy arrays and similar to native Python lists."""
        if isinstance(value, np.ndarray):
            return value.flatten().tolist()
        elif isinstance(value, (list, tuple)):
            return [BoardPoseJSONRecorder._to_list(v) for v in value]
        elif isinstance(value, (np.integer, np.floating)):
            return float(value) if isinstance(value, np.floating) else int(value)
        else:
            return value

    @staticmethod
    def _write_json_atomic(filename: str, data: Dict):
        """
        Write JSON file atomically (write to temp file, then rename).

        Prevents corruption if process crashes during write.
        """
        temp_filename = filename + ".tmp"

        try:
            with open(temp_filename, 'w') as f:
                json.dump(data, f, indent=2)

            # Atomic rename
            if os.path.exists(filename):
                os.remove(filename)
            os.rename(temp_filename, filename)

        except Exception as e:
            if os.path.exists(temp_filename):
                try:
                    os.remove(temp_filename)
                except:
                    pass
            raise e

    def poses_get(self) -> List[Dict]:
        """Get list of recorded poses for this session."""
        return self.poses

    def get_json_file_path(self) -> str:
        """Get path to the JSON file (None if no poses recorded yet)."""
        return self.json_filename

    def reset_for_new_session(self):
        """Reset recorder state (called when starting a new recording session)."""
        # Don't reset poses - they accumulate for the session
        # Just log that we're starting a new pose recording
        logger.info(f"🔄 Recording new board pose #{len(self.poses) + 1}")

    def get_session_folder(self) -> str:
        """Get the session folder path for this recorder."""
        return self.session_folder

    def get_cop_data_dir(self) -> str:
        """Get the CoP data directory path."""
        return self.cop_data_dir

    def get_foot_data_dir(self) -> str:
        """Get the foot data directory path."""
        return self.foot_data_dir


# Global instance for module-level usage (like COP_wifi_data pattern)
_recorder_instance = None


def initialize_recorder(patient_name: str, trial_path: str) -> BoardPoseJSONRecorder:
    """
    Initialize the global recorder instance.

    Args:
        patient_name: Name of the patient
        trial_path: Path to trial folder or session folder

    Returns:
        BoardPoseJSONRecorder instance
    """
    global _recorder_instance
    try:
        logger.info(f"📋 initialize_recorder called: patient='{patient_name}', trial_path='{trial_path}'")
        print(f"📋 initialize_recorder called: patient='{patient_name}', trial_path='{trial_path}'")

        _recorder_instance = BoardPoseJSONRecorder(patient_name, trial_path)

        logger.info(f"✅ Recorder instance created successfully")
        logger.info(f"   Session folder: {_recorder_instance.session_folder}")
        logger.info(f"   Board_Data dir: {_recorder_instance.board_data_dir}")
        logger.info(f"   CoP_Data dir: {_recorder_instance.cop_data_dir}")
        logger.info(f"   Foot_Data dir: {_recorder_instance.foot_data_dir}")
        logger.info(f"   JSON file: {_recorder_instance.json_filename}")

        print(f"✅ Recorder instance created successfully")
        print(f"   Session folder: {_recorder_instance.session_folder}")
        print(f"   Board_Data dir: {_recorder_instance.board_data_dir}")
        print(f"   CoP_Data dir: {_recorder_instance.cop_data_dir}")
        print(f"   Foot_Data dir: {_recorder_instance.foot_data_dir}")
        print(f"   JSON file: {_recorder_instance.json_filename}")

        return _recorder_instance
    except Exception as e:
        logger.error(f"❌ FAILED to initialize recorder: {e}", exc_info=True)
        print(f"❌ FAILED to initialize recorder: {e}")
        raise


def get_recorder() -> BoardPoseJSONRecorder:
    """Get the global recorder instance."""
    return _recorder_instance


def set_board_layout(layout_data: Dict[str, Any]):
    """Set board layout on the global recorder instance."""
    if _recorder_instance:
        _recorder_instance.set_board_layout(layout_data)
    else:
        logger.warning("❌ Board pose recorder not initialized")


def record_board_pose_global(board_position_list: List[Dict],
                             cop_csv_path: Optional[str] = None,
                             foot_csv_path: Optional[str] = None) -> str:
    """
    Record board pose using global recorder instance.

    Args:
        board_position_list: List of board data dicts
        cop_csv_path: Optional relative path to CoP data CSV file
        foot_csv_path: Optional relative path to foot data CSV file

    Returns:
        Path to JSON file
    """
    logger.debug(f"🔍 record_board_pose_global called: {len(board_position_list) if board_position_list else 0} boards")
    print(f"🔍 record_board_pose_global called: {len(board_position_list) if board_position_list else 0} boards")
    print(f"🔍 _recorder_instance = {_recorder_instance}")

    if _recorder_instance:
        logger.debug(f"🔍 Recorder is initialized - calling record_board_pose()")
        print(f"🔍 Recorder is initialized - calling record_board_pose()")
        result = _recorder_instance.record_board_pose(
            board_position_list,
            cop_csv_path=cop_csv_path,
            foot_csv_path=foot_csv_path
        )
        logger.info(f"✅ record_board_pose_global returned: {result}")
        print(f"✅ record_board_pose_global returned: {result}")
        return result
    else:
        logger.warning("❌ Board pose recorder not initialized - cannot save board pose")
        print("❌ Board pose recorder not initialized - cannot save board pose")
        return None
