"""
board_pose_json_recorder.py

Saves board pose data to Board_Poses.json.

The caller (COP_wifi_data) provides the exact board_data_dir path.
This module does NO folder-creation logic — SessionManager owns that.

Output file: <board_data_dir>/Board_Poses.json
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
import numpy as np

logger = logging.getLogger(__name__)


class BoardPoseJSONRecorder:
    """
    Records board pose data to a Board_Poses.json file.

    One instance per pose (Pose1, Pose2, …).  Created fresh each time
    recording starts for a new pose; accumulates across trial recordings
    within the same pose.
    """

    def __init__(self, patient_name: str, board_data_dir: str):
        """
        Args:
            patient_name   : Patient ID string (metadata only)
            board_data_dir : Absolute path to the Board_Data/ folder
                             e.g. …/Assessment/Pose1/Board_Data/
                             The folder must already exist (SessionManager creates it).
        """
        self.patient_name   = patient_name
        self.board_data_dir = board_data_dir

        os.makedirs(board_data_dir, exist_ok=True)   # safety

        self.json_filename      = os.path.join(board_data_dir, "Board_Poses.json")
        self.board_layout_data  = None
        self.poses: List[Dict]  = []

        # Load existing poses if JSON already exists (across recording restarts)
        self._load_existing()

        logger.info(f"📋 BoardPoseJSONRecorder ready → {self.json_filename}")

    # ─────────────────────────────────────────────────────────────────────────

    def set_board_layout(self, layout_data: Dict[str, Any]):
        self.board_layout_data = layout_data

    def record_board_pose(self, board_position_list: List[Dict]) -> str:
        """
        Append a board pose entry to Board_Poses.json.

        Args:
            board_position_list: Raw board data list from COP_wifi_data

        Returns:
            Path to the JSON file written.
        """
        try:
            pose_entry = {
                "timestamp":  datetime.now().isoformat(),
                "board_data": self._format_board_data(board_position_list),
            }
            self.poses.append(pose_entry)

            json_data = {
                "metadata": {
                    "patient_name": self.patient_name,
                    "board_data_dir": self.board_data_dir,
                    "created_at":  datetime.now().isoformat(),
                    "total_poses": len(self.poses)
                },
                "poses": self.poses
            }
            if self.board_layout_data:
                json_data["board_layout"] = self.board_layout_data

            self._write_json_atomic(self.json_filename, json_data)
            logger.info(f"💾 Board pose {len(self.poses)} saved → {self.json_filename}")
            return self.json_filename

        except Exception as e:
            logger.error(f"❌ record_board_pose failed: {e}", exc_info=True)
            raise

    # ─────────────────────────────────────────────────────────────────────────

    def _load_existing(self):
        try:
            if os.path.exists(self.json_filename):
                with open(self.json_filename, 'r') as f:
                    data = json.load(f)
                self.poses = data.get('poses', [])
                if 'board_layout' in data:
                    self.board_layout_data = data['board_layout']
                logger.info(f"♻️  Loaded {len(self.poses)} existing poses from {self.json_filename}")
        except Exception as e:
            logger.warning(f"⚠️  Could not load existing poses: {e}")

    @staticmethod
    def _format_board_data(board_position_list: List[Dict]) -> List[Dict]:
        formatted = []
        for data in board_position_list:
            formatted.append({
                "board_translation": BoardPoseJSONRecorder._to_list(data.get("board_translation")),
                "ip_address":        str(data.get("ip_address", "")).strip(),
                "angle":             BoardPoseJSONRecorder._to_list(data.get("angle")),
                "rotation_matrix":   BoardPoseJSONRecorder._to_list(data.get("rotation_matrix")),
                "board_aruco_ids":   BoardPoseJSONRecorder._to_list(data.get("board_aruco_ids")),
            })
        return formatted

    @staticmethod
    def _to_list(value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.flatten().tolist()
        elif isinstance(value, (list, tuple)):
            return [BoardPoseJSONRecorder._to_list(v) for v in value]
        elif isinstance(value, (np.integer, np.floating)):
            return float(value) if isinstance(value, np.floating) else int(value)
        return value

    @staticmethod
    def _write_json_atomic(filename: str, data: Dict):
        temp = filename + ".tmp"
        try:
            with open(temp, 'w') as f:
                json.dump(data, f, indent=2)
            if os.path.exists(filename):
                os.remove(filename)
            os.rename(temp, filename)
        except Exception as e:
            if os.path.exists(temp):
                try:
                    os.remove(temp)
                except Exception:
                    pass
            raise e