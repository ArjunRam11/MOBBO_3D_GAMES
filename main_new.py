#!/usr/bin/env python3
"""
MOBBO 3D Motion Analysis System — 4-Point Foot Model
Primary application file.

Pipeline:
  Godot launches Python → boards detected → ArUco3DVisualizer opens
  Godot login sends patient ID via UDP → Python fills name field
  Operator presses "Start Recording" (or Godot sends start_recording command)
  CoP + Board Pose + Foot data saved under Mobbo_data/<patient_id>/session_.../
  CoP streamed live to Godot (port 8000) for game control
  Two-way commands via port 9000 (Godot→Python) and 9001 (Python→Godot)
"""

import sys
import os
import time
import threading
import logging
import json
import socket
import select
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from contextlib import contextmanager
from fileloader import *
import numpy as np
np.set_printoptions(precision=3, suppress=True)
import math
import cv2
from PyQt5 import QtWidgets, QtCore

from Graph_window_main import (
    ArUco3DVisualizer, data_lock, pose_3d_keypoints, gcop1, angles,
    left_heel_vector, left_toe_vector, right_heel_vector, right_toe_vector,
    MAT, DIST, pose, keypoints, varboard, referenceboard
)
from loading_process_widget import LoadingWindow, BOSWorker, ResetButtonProcess
from board_update_plot_graph import BoardMeshPlotter
from Frame_Process import Frame_Process
from board_pose_estimator import board_pose_estimator
from foot_process4pt import foot_detector
from foot_recorder import FootDataRecorder
from base_of_support_lib import (
    get_any_3d_points, get_rectangle_corners_3d, plot_rectangle_3d_points
)
from sea_library import (
    return_BOS_vectors_singlekeypoint, get_keypoints_3d_sealibrary,
    get_all_angles_from_18x3
)
from pyqtlibrary import (
    create_foot_polygon_3d, return_BOS_vectors_singlekeypoint_pyqt
)
from noisecancellation import update_buffer
from COP_wifi_data import MobboData, get_mobbo_instance
from godot_bridge import GodotBridgeHelper
from board_layout_analyzer import analyze_board_layout, format_layout_for_godot
from session_manager import get_session_manager


# ════════════════════════════════════════════════════════════════════════════════
# FOOT GEOMETRY CONSTANTS
# ════════════════════════════════════════════════════════════════════════════════

FOOT_LENGTH = 0.26   # metres
FOOT_WIDTH  = 0.10   # metres

_foot_geometry_path = fr'e:\OpenCV_mobbo_works\BaseOfSupport\notebooks\BOS_validation'
FootGeometryfile    = 'normalized_projected_vectors.pickle'
FootGeometryPath    = os.path.join(_foot_geometry_path, "FootModelMocapData")
foot_normalized_projected_vectors = read_pickle(FootGeometryPath, FootGeometryfile)

RIGID_BODY_REF_FILE = 'rigid_body_vectors_new.pkl'
RIGID_BODY_REF_PATH = fr'E:\OpenCV_mobbo_works\BaseOfSupport\notebooks\BOS_validation\FootModelMocapData'


# ════════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ════════════════════════════════════════════════════════════════════════════════

CONFIG = {
    'SLEEP_INTERVALS': {
        'BOS_LOOP': 0.008,
        'ARUCO_LOOP': 0.005,
        'BOARD_SETUP': 0.3,
        'ERROR_RECOVERY': 0.1
    },
    'FOOT_PARAMS': {
        'LENGTH': 0.26, 'WIDTH': 0.1, 'TOE_WIDTH': 0.1, 'HEIGHT': 0.020
    },
    'ROTATION_180': np.array([[-1, 0, 0], [0, -1, 0], [0, 0, 1]], dtype=np.float32),
    'BOARD_DIMS': {
        'LENGTH_M': 0.6,
        'BREADTH_M': 0.45
    },
    'COP_CALIB': {
        'UNIT_SCALE': 100.0,
        'X_SCALE': 1.0,
        'Y_SCALE': 1.0,
        'X_OFFSET_M': 0.0,
        'Y_OFFSET_M': 0.0,
        'CLAMP_TO_BOARD': True
    },
    'CAMERA_DIMS': (1280, 720),
    # UDP ports
    'UDP': {
        'GODOT_DATA_PORT': 8000,       # Python → Godot (CoP + board pose)
        'GODOT_CAMERA_PORT': 8001,     # Python → Godot (camera, disabled)
        'COMMAND_LISTEN_PORT': 9000,   # Godot → Python (commands)
        'ACK_SEND_PORT': 9001,         # Python → Godot (acknowledgements)
    }
}

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

stop_threads    = False
stop_flag_aruco = False
process_complete = False


# ════════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ════════════════════════════════════════════════════════════════════════════════

@dataclass
class ThreadState:
    bos_running:    bool = False
    aruco_running:  bool = False
    stop_requested: bool = False


@dataclass
class BoardData:
    points_3d:             Dict[int, np.ndarray] = field(default_factory=dict)
    translations:          Dict[int, np.ndarray] = field(default_factory=dict)
    rotations:             Dict[int, np.ndarray] = field(default_factory=dict)
    ip_addresses:          Dict[int, str]        = field(default_factory=dict)
    relative_translations: Dict[int, np.ndarray] = field(default_factory=dict)
    relative_rotations:    Dict[int, np.ndarray] = field(default_factory=dict)
    reference_ip:          Optional[str]         = None
    reference_id:          Optional[int]         = None
    reference_translation: Optional[np.ndarray]  = None
    reference_rotation:    Optional[np.ndarray]  = None


# ════════════════════════════════════════════════════════════════════════════════
# STANDALONE HELPER FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════════

def sanitize_fbp_data(keypoints_3d):
    if keypoints_3d is None:
        return None
    if not isinstance(keypoints_3d, np.ndarray): 
        return None
    if np.all(np.isnan(keypoints_3d)):
        return None
    fbp_points = []
    for row in keypoints_3d:
        if len(row) >= 3:
            x = None if np.isnan(row[0]) else float(row[0])
            y = None if np.isnan(row[1]) else float(row[1])
            z = None if np.isnan(row[2]) else float(row[2])
            if x is not None or y is not None or z is not None:
                fbp_points.append({'x': x, 'y': y, 'z': z})
            else:
                fbp_points.append(None)
    return fbp_points if any(pt is not None for pt in fbp_points) else None


def sanitize_for_json(data):
    if isinstance(data, dict):
        return {k: sanitize_for_json(v) for k, v in data.items()}
    elif isinstance(data, (list, tuple)):
        sanitized = [sanitize_for_json(item) for item in data]
        return None if all(x is None for x in sanitized) else sanitized
    elif isinstance(data, np.ndarray):
        if np.all(np.isnan(data)) or data.size == 0:
            return None
        return sanitize_for_json(data.tolist())
    elif isinstance(data, (np.floating, float)):
        return None if (math.isnan(data) or math.isinf(data)) else float(data)
    elif isinstance(data, (np.integer, int)):
        return int(data)
    elif data is None:
        return None
    else:
        return data


def validate_polygon_data(polygon_data):
    if polygon_data is None:
        return None
    if isinstance(polygon_data, np.ndarray):
        if polygon_data.size == 0 or np.all(np.isnan(polygon_data)):
            return None
        valid_rows = []
        for row in polygon_data:
            if len(row) >= 3 and not np.isnan(row).any():
                valid_rows.append([float(row[0]), float(row[1]), float(row[2])])
        return valid_rows if len(valid_rows) >= 3 else None
    return None


def return_BOS_vectors_4(tvec_var, rvec_var, tvec_ref, rvec_ref, *input_vectors):
    rot_ref = (cv2.Rodrigues(rvec_ref)[0]
               if np.asarray(rvec_ref).shape != (3, 3)
               else np.asarray(rvec_ref, dtype=np.float64))
    rot_var = (cv2.Rodrigues(rvec_var)[0]
               if np.asarray(rvec_var).shape != (3, 3)
               else np.asarray(rvec_var, dtype=np.float64))

    tvec_var = np.asarray(tvec_var, dtype=np.float64).reshape(3, 1)
    tvec_ref = np.asarray(tvec_ref, dtype=np.float64).reshape(3, 1)

    relative_orientation = np.matmul(rot_ref.T, rot_var)
    trans_var_ref        = np.matmul(rot_ref.T, (tvec_var - tvec_ref))

    out = []
    for vec in input_vectors:
        vec     = np.asarray(vec, dtype=np.float64).reshape(3, 1)
        vec_var = np.matmul(rot_var.T, (vec - tvec_var))
        vec_rot = np.matmul(relative_orientation.T, vec_var)
        vec_ref = vec_rot + trans_var_ref
        out.append(vec_ref.reshape(1, 3))
    return out


def recover_rigid_transform(P: np.ndarray, Q: np.ndarray):
    """
    Recover rotation R and translation t such that Q ≈ R @ P + t.

    P : (N, D) reference points
    Q : (N, D) detected  points
    Returns R (D×D rotation matrix) and t (D,) translation vector.
    """
    assert P.shape == Q.shape, "Point sets must have the same shape"
    centroid_P = P.mean(axis=0)
    centroid_Q = Q.mean(axis=0)
    P_c = P - centroid_P
    Q_c = Q - centroid_Q
    H   = P_c.T @ Q_c
    U, S, Vt = np.linalg.svd(H)
    R = Vt.T @ U.T
    if np.linalg.det(R) < 0:
        Vt[-1, :] *= -1
        R = Vt.T @ U.T
    t = centroid_Q - R @ centroid_P
    return R, t


def ReconstructFootFromNormalizedVectors(normalized_vecs, key1, key2, key3,
                                         foot_length, forefoot_width):
    def _flat2(v):
        return np.asarray(v, dtype=np.float64).flatten()[:2]

    meta1     = _flat2(key1)
    meta3     = _flat2(key2)
    navicular = _flat2(key3)

    v1    = meta3 - meta1
    norm1 = np.linalg.norm(v1)
    if norm1 < 1e-9:
        return np.full((len(normalized_vecs[0]), 2), np.nan)
    x_axis = v1 / norm1

    v2        = navicular - meta1
    proj_on_x = np.dot(v2, x_axis) * x_axis
    y_temp    = v2 - proj_on_x
    norm2     = np.linalg.norm(y_temp)
    if norm2 < 1e-9:
        return np.full((len(normalized_vecs[0]), 2), np.nan)
    y_axis = y_temp / norm2

    pts = []
    for norm_vec in normalized_vecs[0]:
        nv        = np.asarray(norm_vec, dtype=np.float64)
        global_pt = meta1 + nv[0] * forefoot_width * x_axis + nv[1] * foot_length * y_axis
        pts.append(global_pt)

    return np.array(pts)


# ════════════════════════════════════════════════════════════════════════════════
# HELPER MANAGER CLASSES
# ════════════════════════════════════════════════════════════════════════════════

class CoordinateTransformer:
    """
    Transforms raw board CoP (copx, copy) into the 3D board frame.

    Logic matches the original working version exactly:
      1. Build [copx, copy, 0] column vector
      2. Apply 180-degree rotation (flip X and Y axes)
      3. Divide by 100 to convert mm → m
    No clamping, no offsets — these distort the plot.
    """
    _rotation_180 = np.array([[-1, 0, 0], [0, -1, 0], [0, 0, 1]], dtype=np.float64)

    def local_cop_to_board_frame(self, copx: float, copy: float) -> np.ndarray:
        cop = np.array([copx, copy, 0], dtype=np.float64).reshape(3, 1)
        return np.matmul(self.rotation_180.T, cop) / 100.0

    @property
    def rotation_180(self):
        return self._rotation_180

    @staticmethod
    def _find_board_id_by_ip(ip_dict, target_ip):
        for board_id, ip_addr in ip_dict.items():
            if str(ip_addr).strip().lower() == target_ip:
                return board_id
        return None


class ThreadManager:
    def __init__(self):
        self.state    = ThreadState()
        self._threads = {}
        self._lock    = threading.RLock()

    def start_thread(self, name: str, target, args=()) -> bool:
        with self._lock:
            if name in self._threads and self._threads[name].is_alive():
                logger.warning(f"Thread {name} already running")
                return False
            thread = threading.Thread(target=target, args=args, daemon=True)
            thread.start()
            self._threads[name] = thread
            logger.info(f"Started thread: {name}")
            return True

    def stop_all(self):
        self.state.stop_requested = True
        with self._lock:
            for name, thread in self._threads.items():
                if thread.is_alive():
                    try:
                        thread.join(timeout=2.0)
                    except Exception as e:
                        logger.error(f"Error stopping thread {name}: {e}")
            self._threads.clear()
        logger.info("All threads stopped")


# ════════════════════════════════════════════════════════════════════════════════
# GODOT ACK SENDER  — Python → Godot port 9001
# ════════════════════════════════════════════════════════════════════════════════

def send_ack_to_godot(payload: dict):
    """Send a JSON acknowledgement/status packet to Godot on port 9001."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        msg  = json.dumps(payload).encode('utf-8')
        sock.sendto(msg, ("127.0.0.1", CONFIG['UDP']['ACK_SEND_PORT']))
        sock.close()
        logger.debug(f"ACK sent to Godot: {payload}")
    except Exception as e:
        logger.warning(f"Failed to send ACK to Godot: {e}")


# ════════════════════════════════════════════════════════════════════════════════
# BOSEstimator — central coordinator
# ════════════════════════════════════════════════════════════════════════════════

class BOSEstimator:
    """
    Central coordinator for the MOBBO 3D analysis system.

    Responsibilities:
      - Board detection and CoP streaming to Godot (port 8000)
      - Bidirectional command channel with Godot (ports 9000 / 9001)
      - Patient session management (name pre-fill from Godot login)
      - Recording control: start/stop from Python UI or Godot game command
      - Saving CoP CSVs, Board_Poses.json and foot data into session folder
    """

    def __init__(self, frame: Frame_Process):
        self.frame  = frame
        self.mobbo  = get_mobbo_instance()
        logger.info(f"✅ BOSEstimator using MobboData singleton: {self.mobbo}")

        self.foot_detection_model = foot_detector()
        self.recorder             = FootDataRecorder()
        self.coord_transformer    = CoordinateTransformer()

        # Load rigid-body reference keypoints for foot alignment (optional)
        self._rigid_ref = None
        try:
            import pickle as _pkl
            _rbd_path = os.path.join(RIGID_BODY_REF_PATH, RIGID_BODY_REF_FILE)
            with open(_rbd_path, 'rb') as _f:
                _rbd = _pkl.load(_f)
            # Right foot reference — 2D XY only (meta1=big_toe, meta3=mid, meta5=pinky, navicular=heel)
            r_ref = np.array([
                _rbd['r_meta1'][:2],
                _rbd['r_meta3'][:2],
                _rbd['r_meta5'][:2],
                _rbd['r_navicular'][:2],
            ], dtype=np.float64)  # (4, 2)
            # Left foot reference — mirror X to match the right-foot coordinate convention
            l_ref = np.array([
                [-_rbd['l_meta1'][0],     _rbd['l_meta1'][1]],
                [-_rbd['l_meta3'][0],     _rbd['l_meta3'][1]],
                [-_rbd['l_meta5'][0],     _rbd['l_meta5'][1]],
                [-_rbd['l_navicular'][0], _rbd['l_navicular'][1]],
            ], dtype=np.float64)  # (4, 2)
            self._rigid_ref = {'right': r_ref, 'left': l_ref}
            logger.info("✅ Rigid-body reference keypoints loaded for foot alignment")
        except Exception as _e:
            logger.warning(f"Rigid-body reference not loaded — foot alignment disabled: {_e}")
        self.thread_manager       = ThreadManager()

        self.board_data               = BoardData()
        self.board_pose_mesh_plotter  = None
        self.visualizer               = None
        self.previous_board_pose_hash = None
        self.board_pose_sent          = False

        self.foot_numpy_points   = [None, None]
        self.foot_scatter_points = [None, None]
        self.all_cops            = []
        self.total_weight        = 0.0
        self._initialized        = False
        self.counter             = 0

        # Legacy attributes kept for backward compatibility
        self.board_points_3d     = {}
        self.reference_board_id  = None
        self.left_foot_polygon_point  = None
        self.right_foot_polygon_point = None
        self.board_pose          = board_pose_estimator()

        self.bos_thread           = None
        self.bos_thread_running   = False
        self.aruco_thread_        = None
        self.aruco_thread_running = True
        self.Cop_thread           = None
        self.Cop_thread_running   = True

        self.board_point_lock = threading.Lock()
        self.data_lock        = threading.Lock()

        # ── Godot data bridge (Python → Godot port 8000) ─────────────────
        self.godot_bridge = GodotBridgeHelper(
            gcop_array=gcop1,
            data_lock=self.data_lock,
            godot_ip="127.0.0.1",
            godot_port=CONFIG['UDP']['GODOT_DATA_PORT'],
            godot_port_camera=CONFIG['UDP']['GODOT_CAMERA_PORT'],
            data_format="json"
        )

        # ── Command socket (Godot → Python port 9000) ────────────────────
        self._command_socket = None
        self._init_command_socket()

        # ── DataLogging ref (set after visualizer is built) ───────────────
        self._data_logging        = None
        self._pending_patient_id  = None
        self._current_patient_id  = None
        self._active_game_cop_path = None   # tracks active game recording path
        self._bos_before_game      = None

        self.bos_enabled = True  # BOS toggle: when False, skip foot/pose computation
        self.foot_process_enabled = True
        self._foot_frame_source = None

        logger.info("BOSEstimator initialised (4-point foot model)")

    # ─────────────────────────────────────────────────────────────────────────
    # Initialisation helpers
    # ─────────────────────────────────────────────────────────────────────────

    def set_visualizer(self, visualizer):
        self.visualizer = visualizer

    def set_data_logging(self, data_logging):
        """Called from main() after the visualizer (and its DataLogging) are ready."""
        self._data_logging = data_logging
        if self._pending_patient_id:
            logger.info(f"👤 Applying pending patient: '{self._pending_patient_id}'")
            self._apply_patient_id(self._pending_patient_id)
            self._pending_patient_id = None

    def _init_command_socket(self):
        """Bind UDP socket on port 9000 to receive commands from Godot."""
        try:
            if self._command_socket:
                try:
                    self._command_socket.close()
                except Exception:
                    pass
                self._command_socket = None

            self._command_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._command_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._command_socket.bind(("127.0.0.1", CONFIG['UDP']['COMMAND_LISTEN_PORT']))
            self._command_socket.setblocking(False)
            print(f"✅ Command listener ready on UDP port {CONFIG['UDP']['COMMAND_LISTEN_PORT']}")
        except Exception as e:
            print(f"❌ Command socket init failed: {e}")
            self._command_socket = None

    # ─────────────────────────────────────────────────────────────────────────
    # Patient management
    # ─────────────────────────────────────────────────────────────────────────

    def _apply_patient_id(self, patient_id: str):
        """
        Pre-fill the Python UI name field with the patient ID from Godot.
        Also starts the session in SessionManager (creates the session folder once).
        """
        self._current_patient_id = patient_id
        # Start session — idempotent, safe to call multiple times for same patient
        get_session_manager().start_session(patient_id)
        if self._data_logging is not None:
            self._data_logging.set_patient_from_godot(patient_id)
            print(f"✅ Python UI pre-filled with patient: '{patient_id}'")
            send_ack_to_godot({
                "type": "patient_ack",
                "patient_id": patient_id,
                "status": "received",
                "timestamp": time.time()
            })
        else:
            self._pending_patient_id = patient_id
            print(f"⏳ UI not ready — patient '{patient_id}' stored for later")

    # ─────────────────────────────────────────────────────────────────────────
    # Recording control (called from Godot game commands)
    # ─────────────────────────────────────────────────────────────────────────

    def set_bos_enabled(self, enabled: bool, reason: str = ""):
        """
        Enable/disable BOS + foot processing without stopping CoP/game control.
        This is intentionally separate from stop_all_threads().
        """
        enabled = bool(enabled)
        if self.bos_enabled == enabled and self.foot_process_enabled == enabled:
            return

        self.bos_enabled = enabled
        self.foot_process_enabled = enabled

        if enabled:
            if self._foot_frame_source is not None:
                self.foot_detection_model.start_detection(self._foot_frame_source)
            print(f"🦶 Foot/BOS processing ENABLED{f' ({reason})' if reason else ''}")
        else:
            self.foot_detection_model.foot_prediction_stopthread()
            self.left_foot_polygon_point = None
            self.right_foot_polygon_point = None
            self.foot_numpy_points = [None, None]
            self.foot_scatter_points = [None, None]
            self.mobbo.set_foot_points(None, None)
            self.godot_bridge.update_BoS_points(None, None)
            print(f"🦶 Foot/BOS processing DISABLED{f' ({reason})' if reason else ''}")

    def _start_recording_from_godot(self, game_name: str = "UnknownGame"):
        """
        Start recording triggered by a Godot game event.
        Uses the Games/ hierarchy via DataLogging.start_game_recording().
        """
        if self._data_logging is None:
            logger.warning("⚠️ Cannot start recording — DataLogging not ready")
            return

        try:
            cop_path = self._data_logging.start_game_recording(game_name=game_name)
            if cop_path:
                self._active_game_cop_path = cop_path
                self._bos_before_game = self.bos_enabled
                self.set_bos_enabled(False, reason="game recording")
                print(f"▶️  Game recording STARTED by Godot: {cop_path}")
                send_ack_to_godot({
                    "type": "recording_ack",
                    "status": "started",
                    "patient_id": self._current_patient_id,
                    "game": game_name,
                    "timestamp": time.time()
                })
        except Exception as e:
            logger.error(f"Failed to start game recording from Godot: {e}")

    def _stop_recording_from_godot(self):
        """Stop recording triggered by a Godot game event."""
        if self._data_logging is None:
            return
        try:
            cop_path = getattr(self, '_active_game_cop_path', None)
            self._data_logging.stop_game_recording(cop_path)
            self._active_game_cop_path = None
            restore_bos = True if self._bos_before_game is None else self._bos_before_game
            self._bos_before_game = None
            self.set_bos_enabled(restore_bos, reason="game recording stopped")
            print("⏹️  Game recording STOPPED by Godot command")
            send_ack_to_godot({
                "type": "recording_ack",
                "status": "stopped",
                "patient_id": self._current_patient_id,
                "timestamp": time.time()
            })
        except Exception as e:
            logger.error(f"Failed to stop game recording from Godot: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # Command dispatcher — handles all incoming Godot commands
    # ─────────────────────────────────────────────────────────────────────────

    def _handle_command(self, command: dict):
        """
        Dispatch a parsed JSON command received from Godot.

        Supported commands:
          { "type": "set_patient",   "patient_id": "<id>" }
          { "type": "game_selected",  "game_name": "<name>" }  ← creates Games/<name>/PoseN/ folders
          { "type": "start_recording","game_name": "<name>" }
          { "type": "stop_recording"  }
          { "type": "reset_board",    "action": "stop_all_threads" }
          { "type": "app_control",    "action": "shutdown" }
        """
        cmd_type = command.get('type', '')
        action   = command.get('action', '')

        # ── Patient ID from Godot login ────────────────────────────────────
        if cmd_type == 'set_patient':
            patient_id = command.get('patient_id', '').strip()
            if patient_id:
                print(f"👤 Godot SET_PATIENT: '{patient_id}'")
                self._apply_patient_id(patient_id)

        # ── Game folder pre-creation (when player selects a game) ──────────
        elif cmd_type == 'game_selected':
            game_name = command.get('game_name', '').strip()
            if game_name:
                mgr = get_session_manager()
                if mgr.session_path:
                    pose_dir = os.path.join(
                        mgr.session_path, 'Games', game_name, f'Pose{mgr.pose_number}'
                    )
                    for sub in ['Board_Data', 'CoP_Data', 'Foot_Data']:
                        os.makedirs(os.path.join(pose_dir, sub), exist_ok=True)
                    print(f'📁 Game folder pre-created: {pose_dir}')
                    send_ack_to_godot({
                        'type': 'game_folder_ready',
                        'game_name': game_name,
                        'timestamp': time.time()
                    })
                else:
                    print(f'⚠️  No active session — cannot create game folder for {game_name}')

        # ── Recording control from Godot game ─────────────────────────────
        elif cmd_type == 'start_recording':
            game_name = command.get('game_name', 'UnknownGame')
            self._start_recording_from_godot(game_name=game_name)

        elif cmd_type == 'stop_recording':
            self._stop_recording_from_godot()

        # ── Board reset ────────────────────────────────────────────────────
        elif cmd_type == 'reset_board' and action == 'stop_all_threads':
            print("🔄 RESET command received — restarting board detection...")
            self.stop_all_threads()
            time.sleep(1)
            self.reset_all_threads()
            return   # break out of compute_COP loop handled in caller

        # ── Legacy toggle_recording (old Godot versions) ───────────────────
        elif action == 'toggle_recording':
            state      = command.get('state', False)
            trial_name = command.get('trial_path', '')
            try:
                if state:
                    self._start_recording_from_godot()
                else:
                    self._stop_recording_from_godot()
            except Exception as e:
                logger.error(f"toggle_recording error: {e}")

        # ── App shutdown ───────────────────────────────────────────────────
        elif cmd_type == 'app_control' and action == 'shutdown':
            print("🛑 Shutdown command received from Godot")
            QtWidgets.QApplication.quit()

        else:
            logger.debug(f"Unknown command: {command}")

    # ─────────────────────────────────────────────────────────────────────────
    # Thread control
    # ─────────────────────────────────────────────────────────────────────────

    def stop_all_threads(self):
        global stop_flag_aruco, stop_threads, process_complete
        stop_flag_aruco  = False
        stop_threads     = False
        process_complete = False

        with data_lock:
            varboard[0]       = [""]
            referenceboard[0] = [" "]

        self.foot_detection_model.foot_prediction_stopthread()
        self.aruco_thread_      = None
        self.bos_thread_running = False

        if self.mobbo:
            self.mobbo.start()
            logger.info("✅ WiFi thread continues during reset")

    def reset_all_threads(self):
        global stop_threads, stop_flag_aruco
        try:
            stop_threads    = True
            stop_flag_aruco = True

            time.sleep(0.2)
            self._init_command_socket()

            if self.mobbo:
                self.mobbo.start()

            self.godot_bridge.board_pose_sent          = False
            self.godot_bridge.previous_board_pose_hash = None

            self.board_pose_detected_set(self.frame)

            self.bos_thread_running = False
            time.sleep(0.1)
            self.bos_thread = threading.Thread(target=self.compute_COP, name="BOS_Thread_RESET")
            self.bos_thread.daemon = False
            self.bos_thread.start()
            self.bos_thread_running = True

            self.aruco_thread_ = threading.Thread(
                target=self.run_aruco,
                args=(self.visualizer, 1280, 720, MAT, DIST, self.frame),
                name="ArUco_Thread_RESET"
            )
            self.aruco_thread_.daemon = False
            self.aruco_thread_.start()

            stop_threads    = False
            stop_flag_aruco = False
            logger.info("✅ RESET complete")

        except Exception as e:
            logger.error(f"reset_all_threads error: {e}")
            try:
                stop_threads    = True
                stop_flag_aruco = True
                time.sleep(0.2)
                self._init_command_socket()
                self.bos_thread_running = False
                time.sleep(0.1)
                self.bos_thread = threading.Thread(target=self.compute_COP)
                self.bos_thread.start()
                self.bos_thread_running = True
                self.aruco_thread_ = threading.Thread(
                    target=self.run_aruco,
                    args=(self.visualizer, 1280, 720, MAT, DIST, self.frame)
                )
                self.aruco_thread_.start()
                stop_threads    = False
                stop_flag_aruco = False
            except Exception as thread_error:
                logger.error(f"Failed to restart threads: {thread_error}")

    def thread_process_all(self, frame):
        global process_complete
        if not self.bos_thread_running:
            self.bos_thread = threading.Thread(target=self.compute_COP)
            self.bos_thread.start()
            self.bos_thread_running = True
            logger.info("BOS / CoP thread started")
            self.godot_bridge.start()
            logger.info("Godot bridge started (port 8000)")

        self.aruco_thread_ = threading.Thread(
            target=self.run_aruco,
            args=(self.visualizer, 1280, 720, MAT, DIST, frame)
        )
        self.aruco_thread_.start()
        process_complete = True
        logger.info("All processing threads started")

    def restart_cop_and_aruco_threads(self):
        """
        Restart ONLY the CoP and ArUco threads after a board reset.
        board_pose_detected_set() has already run — this just restarts
        the data streaming threads. Safe to call unlimited times.
        """
        global stop_threads, stop_flag_aruco
        logger.info("🔄 restart_cop_and_aruco_threads() — restarting streams after reset")

        stop_threads    = True
        stop_flag_aruco = True

        try:
            self._init_command_socket()
        except Exception as e:
            logger.warning(f"Command socket reinit warning: {e}")

        # Godot bridge — start is idempotent
        try:
            self.godot_bridge.start()
        except Exception:
            pass

        # CoP / BOS thread
        self.bos_thread_running = False
        time.sleep(0.1)
        self.bos_thread = threading.Thread(
            target=self.compute_COP, name="BOS_Thread_RESET", daemon=True
        )
        self.bos_thread.start()
        self.bos_thread_running = True
        logger.info("✅ BOS/CoP thread restarted")

        # ArUco + foot detection thread
        self.aruco_thread_ = threading.Thread(
            target=self.run_aruco,
            args=(self.visualizer, 1280, 720, MAT, DIST, self.frame),
            name="ArUco_Thread_RESET", daemon=True
        )
        self.aruco_thread_.start()
        logger.info("✅ ArUco thread restarted")
        logger.info("✅ restart_cop_and_aruco_threads() complete")

    # ─────────────────────────────────────────────────────────────────────────
    # Board detection
    # ─────────────────────────────────────────────────────────────────────────

    def board_pose_detected_set(self, frame):
        global stop_flag_aruco, stop_threads
        print("🔍 board_pose_detected_set() STARTED")

        board_pose_data = self.board_pose.board_pose(frame)
        self.board_position_data = board_pose_data
        self.mobbo.set_board_data(self.board_position_data)
        time.sleep(0.5)

        self.board_points_3d       = {}
        self.board_translations    = {}
        self.board_rotations       = {}
        self.board_ip              = {}
        self.relative_translations = {}
        self.relative_rotations    = {}
        self.ip_addresses          = []
        self.reference_board_ip    = None
        self.reference_board_id    = None

        translations, rotation_matrices, ip_addresses, ids = [], [], [], []

        for i in range(len(board_pose_data)):
            entry = board_pose_data[i][0]
            translations.append(entry['board_translation'].reshape(3, 1))
            rotation_matrices.append(entry['rotation_matrix'].reshape(3, 3))
            ip_addresses.append(entry['ip_address'].strip())
            # Use the first ArUco marker ID as the representative board ID
            # so ids[i] maps 1:1 with translations[i] and ip_addresses[i]
            board_aruco = np.asarray(entry['board_aruco_ids']).flatten().tolist()
            ids.append(int(board_aruco[0]))
            print(f"  Board {i}: IP={entry['ip_address'].strip()} → ArUco ID={int(board_aruco[0])}")

        if len(translations) == 0:
            print("❌ No boards detected")
            return

        print(f"✅ Detected {len(translations)} boards with {len(ids)} IDs")

        # Tell MobboData about discovered board IPs so it can send direct UDP
        self.mobbo.set_board_ips(ip_addresses)

        distances = [t[2, 0] for t in translations]
        ref_index = np.argmin(distances)
        self.reference_board_ip = ip_addresses[ref_index]
        self.reference_board_id = ids[ref_index]

        with self.board_point_lock:
            self.board_points_3d.clear()
            self.board_translations.clear()
            self.board_rotations.clear()
            self.relative_translations.clear()
            self.relative_rotations.clear()
            self.reference_board_translation = None
            self.reference_board_rotation    = None

            for i in range(len(translations)):
                board_ids = ids[i]
                self.board_ip[board_ids]           = ip_addresses[i]
                self.board_translations[board_ids] = translations[i]
                self.board_rotations[board_ids]    = rotation_matrices[i]

                board_points_3d, _ = get_rectangle_corners_3d(
                    translations[i],
                    cv2.Rodrigues(rotation_matrices[i])[0],
                    MAT, DIST,
                    CONFIG['BOARD_DIMS']['LENGTH_M'],
                    CONFIG['BOARD_DIMS']['BREADTH_M']
                )
                self.board_points_3d[board_ids] = plot_rectangle_3d_points(
                    translations[ref_index], cv2.Rodrigues(rotation_matrices[ref_index])[0],
                    translations[ref_index], cv2.Rodrigues(rotation_matrices[ref_index])[0],
                    board_points_3d
                )

                if i != ref_index:
                    ref_rot_T = np.transpose(rotation_matrices[ref_index])
                    self.relative_rotations[board_ids]    = np.matmul(ref_rot_T, rotation_matrices[i])
                    self.relative_translations[board_ids] = np.matmul(ref_rot_T, (translations[i] - translations[ref_index]))

            self.reference_board_translation = translations[ref_index]
            self.reference_board_rotation    = cv2.Rodrigues(rotation_matrices[ref_index])[0]

            if self.counter == 0 and self.visualizer:
                self.board_pose_mesh_update_graph = BoardMeshPlotter(self.visualizer.view)
                self.counter += 1

            if hasattr(self, 'board_pose_mesh_update_graph'):
                self.board_pose_mesh_update_graph.update_boards(self.board_points_3d, self.reference_board_id)

            # Build board XYZ data for Godot
            board_xyz_data = {
                'reference_id': int(self.reference_board_id),
                'boards': {},
                'layout': {}
            }
            board_xyz_data['boards'][str(self.reference_board_id)] = {
                'id': int(self.reference_board_id),
                'relative_rotation_matrix': np.eye(3).flatten().tolist(),
                'relative_translation': [0.0, 0.0, 0.0]
            }
            for board_id in self.relative_rotations.keys():
                board_xyz_data['boards'][str(board_id)] = {
                    'id': int(board_id),
                    'relative_rotation_matrix': self.relative_rotations[board_id].flatten().tolist(),
                    'relative_translation': self.relative_translations[board_id].flatten().tolist()
                }

        # Layout analysis
        try:
            translations_dict = {int(bid): self.board_translations[bid] for bid in self.board_translations}
            layout_info       = analyze_board_layout(translations_dict)
            board_layout_data = format_layout_for_godot(layout_info)
        except Exception:
            board_layout_data = None

        if board_layout_data:
            board_xyz_data['layout'] = {'Board_Layout': board_layout_data.get('layout', 'unknown')}

        self._last_board_xyz_data = board_xyz_data
        self.godot_bridge.update_Boardpose_data(board_xyz_data)
        self.previous_board_pose_hash = self._calculate_board_pose_hash(board_xyz_data)
        self.board_pose_sent = True

        # Advance pose counter in SessionManager (Pose1 on first detection, Pose2 on reset, etc.)
        mgr = get_session_manager()
        if mgr.session_path:
            mgr.next_pose()
            print(f"📐 Board detection complete → now on Pose{mgr.pose_number}")

        stop_flag_aruco = True
        stop_threads    = True

        # Tare all boards once after detection — zeros out sensor offsets
        self.mobbo.tare(n=50)

        if not self._initialized:
            self.thread_process_all(frame)
            self._initialized = True

        print("✅ board_pose_detected_set() COMPLETED")

    def _calculate_board_pose_hash(self, board_data: dict) -> int:
        board_ids = tuple(sorted([int(bid) for bid in board_data['boards'].keys()]))
        return hash((board_data['reference_id'], board_ids))

    def _has_board_configuration_changed(self, current_board_data: dict) -> bool:
        if self.previous_board_pose_hash is None:
            return True
        return self._calculate_board_pose_hash(current_board_data) != self.previous_board_pose_hash

    # ─────────────────────────────────────────────────────────────────────────
    # CoP processing thread  (also handles all Godot → Python commands)
    # ─────────────────────────────────────────────────────────────────────────

    def compute_COP(self):
        """
        Main BOS/CoP thread.

        Runs while stop_threads and stop_flag_aruco are True.
        Every iteration:
          1. Drains command socket (Godot → Python port 9000)
          2. Processes CoP data from WiFi boards
          3. Streams GCoP + local CoPs to Godot (port 8000) via godot_bridge
        """
        global stop_flag_aruco, stop_threads
        print("🔵 compute_COP thread started")

        _reset_requested = False

        while stop_threads and stop_flag_aruco:

            # ── 1. Drain Godot command socket ──────────────────────────────
            if self._command_socket:
                try:
                    ready = select.select([self._command_socket], [], [], 0)
                    if ready[0]:
                        raw, addr = self._command_socket.recvfrom(1024)
                        if raw:
                            try:
                                command = json.loads(raw.decode('utf-8'))
                                print(f"📨 Command from {addr}: {command.get('type','?')}")

                                # Reset must break out of this loop
                                if (command.get('type') == 'reset_board'
                                        and command.get('action') == 'stop_all_threads'):
                                    _reset_requested = True
                                else:
                                    self._handle_command(command)

                            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                                logger.warning(f"Bad command packet: {e}")
                except OSError as e:
                    logger.warning(f"Command socket OS error: {e}")
                except Exception as e:
                    logger.warning(f"Command socket error: {e}")

            if _reset_requested:
                print("🔄 RESET — stopping current threads and re-detecting boards")
                self.stop_all_threads()
                time.sleep(1)
                self.reset_all_threads()
                break

            # ── 2. Process CoP data ────────────────────────────────────────
            if self.mobbo.cop_data:
                _now = time.time()
                addr_keys = [a for a in self.mobbo.cop_data
                             if _now - self.mobbo.cop_timestamps.get(a, 0) < 0.2]

                # ── DEBUG: print every ~2 s to diagnose board-11 issue ────────
                self._dbg_counter = getattr(self, '_dbg_counter', 0) + 1
                if self._dbg_counter >= 200:   # 200 × 10 ms = 2 s
                    self._dbg_counter = 0
                    print(f"\n[DEBUG] cop_data has {len(addr_keys)} board(s): {[a[0] for a in addr_keys]}")
                    print(f"[DEBUG] board_ip map: {self.board_ip}")
                    print(f"[DEBUG] reference IP : {self.reference_board_ip}  (id={self.reference_board_id})")
                    print(f"[DEBUG] relative_rotations keys: {list(self.relative_rotations.keys())}")
                    for addr in addr_keys:
                        copx, copy, w = self.mobbo.cop_data[addr]
                        bip = str(addr[0]).strip().lower()
                        bid = next((k for k, v in self.board_ip.items()
                                    if str(v).strip().lower() == bip), None)
                        print(f"[DEBUG]   {addr[0]}  copx={copx:.2f} copy={copy:.2f} w={w:.3f}  "
                              f"→ board_id_get={bid}  in_rel_rot={bid in self.relative_rotations if bid is not None else False}")
                # ── END DEBUG ──────────────────────────────────────────────────

                if len(addr_keys) >= 1:
                    self.all_cops = []
                    board_weights_by_id = {}
                    ref_ip = str(self.reference_board_ip).strip().lower()

                    # ── Pass 1: reference board first (always index 0) ────────
                    for addr in addr_keys:
                        if str(addr[0]).strip().lower() == ref_ip:
                            copx, copy, w = self.mobbo.cop_data[addr]
                            if self.reference_board_id is not None:
                                board_weights_by_id[int(self.reference_board_id)] = w
                            cop_transformed = self.coord_transformer.local_cop_to_board_frame(copx, copy)
                            self.all_cops.append((cop_transformed, w))
                            break

                    # ── Pass 2: non-reference boards in addr_keys order ───────
                    for addr in addr_keys:
                        board_ip = str(addr[0]).strip().lower()
                        if board_ip != ref_ip:
                            copx, copy, w = self.mobbo.cop_data[addr]
                            cop_transformed = self.coord_transformer.local_cop_to_board_frame(copx, copy)
                            board_id_get = next(
                                (k for k, v in self.board_ip.items()
                                 if str(v).strip().lower() == board_ip), None
                            )
                            if board_id_get is not None:
                                board_weights_by_id[int(board_id_get)] = w
                            if board_id_get is not None and board_id_get in self.relative_rotations:
                                cop_transformed  = np.matmul(self.relative_rotations[board_id_get], cop_transformed)
                                cop_transformed += self.relative_translations[board_id_get]
                            self.all_cops.append((cop_transformed, w))

                    # self.foot_detection_model.update_active_boards(board_weights_by_id)

                    # ── Filter: only boards with weight > 2 kg ────────────────
                    active_cops = [(cv, cw) for cv, cw in self.all_cops if cw > 2]

                    # ── GCoP: weighted average of active boards only ──────────
                    total_weight       = sum(cw for _, cw in active_cops)
                    total_weighted_cop = np.zeros((3, 1))
                    for cv, cw in active_cops:
                        total_weighted_cop += cw * cv
                    Gcop = (total_weighted_cop / total_weight
                            if total_weight > 0 else np.zeros((3, 1)))

                    # Only active boards are displayed and streamed
                    all_cops_display = active_cops

                    # Update Python 3D visualiser
                    if self.visualizer:
                        self.visualizer.cop_and_gcop_update(all_cops_display, total_weight)
                    # Update 2-D split visualiser
                    if hasattr(self, 'visualizer_2d') and self.visualizer_2d:
                        self.visualizer_2d.cop_and_gcop_update(all_cops_display, total_weight)

                    # Update shared array for other modules
                    with data_lock:
                        if gcop1 is not None:
                            gcop1[:] = Gcop.flatten()

                    # ── Print CoP to console (throttled: every ~0.5 s) ──────
                    self._cop_print_counter = getattr(self, '_cop_print_counter', 0) + 1
                    if self._cop_print_counter >= 50:   # 50 × 10 ms ≈ 0.5 s
                        self._cop_print_counter = 0
                        gf = Gcop.flatten()
                        line = f"[CoP] GCoP x={gf[0]:+.1f}  y={gf[1]:+.1f}  W={total_weight:.2f}"
                        for i, (cv, cw) in enumerate(all_cops_display):
                            cf = cv.flatten()
                            line += f"   | Board{i+1}: x={cf[0]:+.1f} y={cf[1]:+.1f} w={cw:.2f}"
                        print(line)

                    # ── 3. Stream to Godot (port 8000) ─────────────────────
                    local_cops_data = []
                    for cop_vec, cop_weight in all_cops_display:
                        f  = cop_vec.flatten()
                        lc = {
                            'x': sanitize_for_json(f[0]),
                            'y': sanitize_for_json(f[1]),
                            'z': sanitize_for_json(f[2]),
                            'weight': sanitize_for_json(cop_weight)
                        }
                        if not all(v is None for v in lc.values()):
                            local_cops_data.append(lc)

                    gf = Gcop.flatten()
                    gcop_data = {
                        'x': sanitize_for_json(gf[0]),
                        'y': sanitize_for_json(gf[1]),
                        'z': sanitize_for_json(gf[2]),
                        'weight': sanitize_for_json(total_weight)
                    }

                    self.godot_bridge.update_cop_data(
                        local_cops=local_cops_data,
                        gcop=gcop_data,
                        total_weight=total_weight
                    )

            time.sleep(0.01)

        self.bos_thread_running = False

    # ─────────────────────────────────────────────────────────────────────────
    # Foot polygon builder
    # ─────────────────────────────────────────────────────────────────────────

    def foot_shape_get_numpy_and_scatter_points(
        self, foot_keys,
        right_big_ref,  right_mid_ref,  right_pinky_ref,  right_heel_ref,
        left_big_ref,   left_mid_ref,   left_pinky_ref,   left_heel_ref
    ):
        self.left_foot_polygon_point  = None
        self.right_foot_polygon_point = None
        self.foot_numpy_points        = [None, None]
        self.foot_scatter_points      = [None, None]

        def _valid(v):
            return v is not None and not np.isnan(np.asarray(v)).any()

        # Set True to use ray-board-plane intersection (corrects parallax).
        # Set False to revert to the original vertical Z-drop.
        USE_RAY_PROJECTION = False

        def _project_to_board_plane(v):
            arr = np.asarray(v, dtype=np.float64).flatten()

            if USE_RAY_PROJECTION:
                # Cast a ray from the camera centre through the foot keypoint
                # and find where it intersects the board plane (Z=0 in board frame).
                # This corrects the inward parallax shift caused by foot height.
                ref_rot = self.reference_board_rotation
                ref_t   = np.asarray(self.reference_board_translation, dtype=np.float64).reshape(3)
                R = (cv2.Rodrigues(ref_rot)[0]
                     if np.asarray(ref_rot).shape != (3, 3)
                     else np.asarray(ref_rot, dtype=np.float64))
                cam_in_board = -(R.T @ ref_t)          # camera origin in board frame
                ray = arr - cam_in_board
                if abs(ray[2]) < 1e-9:                 # ray nearly parallel to board — fall back
                    arr[2] = 0.0
                    return arr.reshape(1, 3)
                scale  = -cam_in_board[2] / ray[2]
                ground = cam_in_board + scale * ray
                ground[2] = 0.0                        # clamp floating-point residual
                return ground.reshape(1, 3)
            else:
                # Original: vertical Z-drop
                arr[2] = 0.0
                return arr.reshape(1, 3)

        if foot_keys:
            # Right foot
            if _valid(right_big_ref) and _valid(right_mid_ref) and _valid(right_heel_ref):
                try:
                    poly_xy = ReconstructFootFromNormalizedVectors(
                        foot_normalized_projected_vectors,
                        _project_to_board_plane(right_big_ref),
                        _project_to_board_plane(right_mid_ref),
                        _project_to_board_plane(right_heel_ref),
                        FOOT_LENGTH, FOOT_WIDTH
                    )
                    if poly_xy is not None and not np.isnan(poly_xy).all():
                        z_col = np.zeros((poly_xy.shape[0], 1))
                        self.foot_numpy_points[0]     = np.hstack([poly_xy, z_col])
                        self.foot_scatter_points[0]   = [
                            _project_to_board_plane(right_big_ref),    # 1st metatarsal
                            _project_to_board_plane(right_mid_ref),    # 3rd metatarsal
                            _project_to_board_plane(right_pinky_ref),  # 5th metatarsal
                            _project_to_board_plane(right_heel_ref),   # navicular
                        ]
                        self.right_foot_polygon_point = poly_xy
                except Exception as e:
                    logger.warning(f"Right foot polygon failed: {e}")

            # Left foot
            if _valid(left_big_ref) and _valid(left_mid_ref) and _valid(left_heel_ref):
                try:
                    poly_xy = ReconstructFootFromNormalizedVectors(
                        foot_normalized_projected_vectors,
                        _project_to_board_plane(left_big_ref),
                        _project_to_board_plane(left_mid_ref),
                        _project_to_board_plane(left_heel_ref),
                        FOOT_LENGTH, FOOT_WIDTH
                    )
                    if poly_xy is not None and not np.isnan(poly_xy).all():
                        z_col = np.zeros((poly_xy.shape[0], 1))
                        self.foot_numpy_points[1]    = np.hstack([poly_xy, z_col])
                        self.foot_scatter_points[1]  = [
                            _project_to_board_plane(left_big_ref),     # 1st metatarsal
                            _project_to_board_plane(left_mid_ref),     # 3rd metatarsal
                            _project_to_board_plane(left_pinky_ref),   # 5th metatarsal
                            _project_to_board_plane(left_heel_ref),    # navicular
                        ]
                        self.left_foot_polygon_point = poly_xy
                except Exception as e:
                    logger.warning(f"Left foot polygon failed: {e}")

            self.mobbo.set_foot_points(self.foot_numpy_points[1], self.foot_numpy_points[0])

            left_clean  = validate_polygon_data(self.foot_numpy_points[1])
            right_clean = validate_polygon_data(self.foot_numpy_points[0])
            if left_clean is not None or right_clean is not None:
                self.godot_bridge.update_BoS_points(left_clean, right_clean)

    # ─────────────────────────────────────────────────────────────────────────
    # ArUco + pose processing thread
    # ─────────────────────────────────────────────────────────────────────────

    def run_aruco(self, visualizer, w, h, mat, dist, frame):
        frame2              = frame
        ref_rotation_matrix = self.reference_board_rotation
        ref_translation     = self.reference_board_translation

        self.foot_detection_model.start_detection(frame2)

        global stop_flag_aruco, stop_threads

        board_check_counter  = 0
        BOARD_CHECK_INTERVAL = 500
        _nan_vec = np.full((1, 3), np.nan, dtype=np.float32)

        while stop_threads and stop_flag_aruco:

            right_big_ref   = _nan_vec.copy()
            right_mid_ref   = _nan_vec.copy()
            right_pinky_ref = _nan_vec.copy()
            right_heel_ref  = _nan_vec.copy()
            left_big_ref    = _nan_vec.copy()
            left_mid_ref    = _nan_vec.copy()
            left_pinky_ref  = _nan_vec.copy()
            left_heel_ref   = _nan_vec.copy()

            foot_keys, depth_frame1, image1 = self.foot_detection_model.get_keypoints()

            # Draw 4 foot keypoints on camera frame
            if foot_keys is not None and image1 is not None:
                _foot_kp_colors = {
                    'right_big_toe': (0, 0, 255),
                    'right_mid':     (0, 128, 255),
                    'right_pinky':   (0, 200, 255),
                    'right_heel':    (0, 255, 200),
                    'left_big_toe':  (255, 0, 0),
                    'left_mid':      (255, 128, 0),
                    'left_pinky':    (255, 200, 0),
                    'left_heel':     (200, 255, 0),
                }
                for kp_name, color in _foot_kp_colors.items():
                    if kp_name in foot_keys:
                        px, py = int(foot_keys[kp_name][0]), int(foot_keys[kp_name][1])
                        cv2.circle(image1, (px, py), 5, color, -1)

            # Periodic board config check
            board_check_counter += 1
            if board_check_counter >= BOARD_CHECK_INTERVAL:
                board_check_counter = 0
                if self.board_pose_sent:
                    current_board_data = {
                        'reference_id': int(self.reference_board_id),
                        'boards': {}
                    }
                    current_board_data['boards'][str(self.reference_board_id)] = {
                        'id': int(self.reference_board_id),
                        'relative_rotation_matrix': np.eye(3).flatten().tolist(),
                        'relative_translation': [0.0, 0.0, 0.0]
                    }
                    for bid in self.relative_rotations:
                        current_board_data['boards'][str(bid)] = {
                            'id': int(bid),
                            'relative_rotation_matrix': self.relative_rotations[bid].flatten().tolist(),
                            'relative_translation': self.relative_translations[bid].flatten().tolist()
                        }
                    if self._has_board_configuration_changed(current_board_data):
                        self.godot_bridge.update_Boardpose_data(current_board_data)
                        self.previous_board_pose_hash = self._calculate_board_pose_hash(current_board_data)

            # Foot keypoints → 3D → reference frame (only when BOS enabled)
            if self.bos_enabled and foot_keys is not None:
                def get_3d(key):
                    if key in foot_keys:
                        return get_any_3d_points(
                            foot_keys[key][0], foot_keys[key][1], depth_frame1, MAT
                        )
                    return None

                r_big_3d   = get_3d('right_big_toe')
                r_mid_3d   = get_3d('right_mid')
                r_pinky_3d = get_3d('right_pinky')
                r_heel_3d  = get_3d('right_heel')
                l_big_3d   = get_3d('left_big_toe')
                l_mid_3d   = get_3d('left_mid')
                l_pinky_3d = get_3d('left_pinky')
                l_heel_3d  = get_3d('left_heel')

                with self.board_point_lock:
                    if self.board_points_3d:

                        if (r_big_3d is not None and r_mid_3d is not None
                                and r_heel_3d is not None
                                and np.any(r_big_3d) and np.any(r_mid_3d) and np.any(r_heel_3d)):
                            r_pinky_safe = (r_pinky_3d
                                            if r_pinky_3d is not None and np.any(r_pinky_3d)
                                            else r_big_3d)
                            try:
                                r_refs = return_BOS_vectors_4(
                                    ref_translation, ref_rotation_matrix,
                                    ref_translation, ref_rotation_matrix,
                                    r_big_3d, r_mid_3d, r_pinky_safe, r_heel_3d
                                )
                                right_big_ref, right_mid_ref, right_pinky_ref, right_heel_ref = r_refs
                                # ── Rigid-body alignment: warp reference shape to detected keypoints ──
                                if self._rigid_ref is not None:
                                    r_c_vec = np.array([
                                        right_big_ref.flatten()[:2],
                                        right_mid_ref.flatten()[:2],
                                        right_pinky_ref.flatten()[:2],
                                        right_heel_ref.flatten()[:2],
                                    ])  # (4, 2) detected in board XY
                                    R_r, t_r = recover_rigid_transform(self._rigid_ref['right'], r_c_vec)
                                    r_aligned = (R_r @ self._rigid_ref['right'].T).T + t_r  # (4, 2)
                                    right_big_ref   = np.array([[r_aligned[0, 0], r_aligned[0, 1], 0.0]])
                                    right_mid_ref   = np.array([[r_aligned[1, 0], r_aligned[1, 1], 0.0]])
                                    right_pinky_ref = np.array([[r_aligned[2, 0], r_aligned[2, 1], 0.0]])
                                    right_heel_ref  = np.array([[r_aligned[3, 0], r_aligned[3, 1], 0.0]])
                            except Exception as e:
                                logger.warning(f"Right BOS transform failed: {e}")

                        if (l_big_3d is not None and l_mid_3d is not None
                                and l_heel_3d is not None
                                and np.any(l_big_3d) and np.any(l_mid_3d) and np.any(l_heel_3d)):
                            l_pinky_safe = (l_pinky_3d
                                            if l_pinky_3d is not None and np.any(l_pinky_3d)
                                            else l_big_3d)
                            try:
                                l_refs = return_BOS_vectors_4(
                                    ref_translation, ref_rotation_matrix,
                                    ref_translation, ref_rotation_matrix,
                                    l_big_3d, l_mid_3d, l_pinky_safe, l_heel_3d
                                )
                                left_big_ref, left_mid_ref, left_pinky_ref, left_heel_ref = l_refs
                                # ── Rigid-body alignment: mirror X → align → un-mirror X ──────────
                                if self._rigid_ref is not None:
                                    def _mx(v):
                                        f = np.asarray(v, dtype=np.float64).flatten()
                                        return np.array([-f[0], f[1]])
                                    l_c_vec = np.array([
                                        _mx(left_big_ref),
                                        _mx(left_mid_ref),
                                        _mx(left_pinky_ref),
                                        _mx(left_heel_ref),
                                    ])  # (4, 2) mirrored detected in board XY
                                    R_l, t_l = recover_rigid_transform(self._rigid_ref['left'], l_c_vec)
                                    l_aligned = (R_l @ self._rigid_ref['left'].T).T + t_l  # (4, 2) mirrored
                                    left_big_ref   = np.array([[-l_aligned[0, 0], l_aligned[0, 1], 0.0]])
                                    left_mid_ref   = np.array([[-l_aligned[1, 0], l_aligned[1, 1], 0.0]])
                                    left_pinky_ref = np.array([[-l_aligned[2, 0], l_aligned[2, 1], 0.0]])
                                    left_heel_ref  = np.array([[-l_aligned[3, 0], l_aligned[3, 1], 0.0]])
                            except Exception as e:
                                logger.warning(f"Left BOS transform failed: {e}")

            if self.bos_enabled:
                self.foot_shape_get_numpy_and_scatter_points(
                    foot_keys,
                    right_big_ref, right_mid_ref, right_pinky_ref, right_heel_ref,
                    left_big_ref,  left_mid_ref,  left_pinky_ref,  left_heel_ref
                )

            # MediaPipe body pose (only when BOS enabled); camera frame always updated
            try:
                _mp_skip = getattr(self, '_mp_skip_counter', 0) + 1
                self._mp_skip_counter = _mp_skip
                if self.bos_enabled and (_mp_skip % 2 == 0):  # run every other frame
                    _t_mp0 = time.time()  # DIAG
                    results = pose.process(cv2.cvtColor(image1, cv2.COLOR_BGR2RGB))
                    _mp_ms  = (time.time() - _t_mp0) * 1000  # DIAG
                    self._mp_diag_count = getattr(self, '_mp_diag_count', 0) + 1
                    self._mp_diag_total = getattr(self, '_mp_diag_total', 0.0) + _mp_ms
                    if self._mp_diag_count % 50 == 0:
                        print(f"[DIAG mediapipe] avg={self._mp_diag_total/self._mp_diag_count:.1f}ms  last={_mp_ms:.1f}ms")
                        self._mp_diag_count = 0; self._mp_diag_total = 0.0

                    if results.pose_landmarks:
                        kp_dict   = get_keypoints_3d_sealibrary(
                            results.pose_landmarks.landmark, depth_frame1, MAT
                        )
                        kp_matrix = np.array([
                            kp_dict[k] if kp_dict[k] is not None else [None, None, None]
                            for k in kp_dict
                        ])
                        corrected_kp = update_buffer(kp_matrix)
                        kp_ref = return_BOS_vectors_singlekeypoint(
                            ref_translation, ref_rotation_matrix,
                            ref_translation, ref_rotation_matrix,
                            corrected_kp
                        )
                        with data_lock:
                            pose_3d_keypoints[:] = kp_ref

                        ang = np.array(get_all_angles_from_18x3(kp_matrix)).reshape((8, 1))
                        with data_lock:
                            angles[:] = ang

                        fbp = sanitize_fbp_data(kp_ref)
                        if fbp is not None and len(fbp) > 0:
                            self.godot_bridge.update_FBP_points_batch(fbp)

                        desired_kp = [
                            'head', 'neck', 'right_shoulder', 'left_shoulder',
                            'right_elbow', 'left_elbow', 'right_hand', 'left_hand',
                            'right_hip', 'left_hip', 'right_knee', 'left_knee',
                            'right_foot', 'left_foot', 'left_heel', 'right_heel',
                            'left_foot_index', 'right_foot_index'
                        ]
                        for key in desired_kp:
                            lm = results.pose_landmarks.landmark[keypoints[key]]
                            cx = int(lm.x * image1.shape[1])
                            cy = int(lm.y * image1.shape[0])
                            cv2.circle(image1, (cx, cy), 2, (0, 255, 0), cv2.FILLED)

                    else:
                        with data_lock:
                            pose_3d_keypoints[:] = np.full((18, 3), np.nan)

                if image1 is not None and self.visualizer:
                    self.visualizer.camera_update(image1)
                    if hasattr(self, 'visualizer_2d') and self.visualizer_2d:
                        self.visualizer_2d.camera_update(image1)

            except Exception:
                pass

            time.sleep(0.001)


# ════════════════════════════════════════════════════════════════════════════════
# APPLICATION ENTRY POINT
# ════════════════════════════════════════════════════════════════════════════════

def show_error_message(error_message: str):
    logger.error(f"Application error: {error_message}")
    try:
        dlg = QtWidgets.QMessageBox()
        dlg.setIcon(QtWidgets.QMessageBox.Critical)
        dlg.setWindowTitle("MOBBO Error")
        dlg.setText("An error occurred during processing:")
        dlg.setInformativeText(error_message)
        dlg.setDetailedText(f"Check logs for more details. Time: {time.strftime('%H:%M:%S')}")
        dlg.setStandardButtons(QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Retry)
        dlg.exec_()
    except Exception as e:
        logger.critical(f"Failed to show error dialog: {e}")
        print(f"CRITICAL ERROR: {error_message}")


def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("MOBBO 3D Motion Analysis")
    app.setApplicationVersion("2.0 – 4pt Foot Model")
    logger.info("Starting MOBBO application...")

    try:
        loading_window = LoadingWindow()
        loading_window.show()

        frame = Frame_Process()
        if not frame.is_camera_connected():
            raise RuntimeError("No RealSense camera detected. Please connect camera and restart.")

        bos_estimator = BOSEstimator(frame)
        visualizer    = ArUco3DVisualizer(bos_estimator)
        bos_estimator.set_visualizer(visualizer)

        # ── 2-D split window (camera feed + top-down CoP/foot/board plot) ─────
        # from visualizer_2d import Visualizer2D
        # bos_estimator.visualizer_2d = Visualizer2D(bos_estimator)

        # Wire DataLogging → enables Godot patient ID to pre-fill the name field
        # and allows Godot game to trigger recording start/stop
        bos_estimator.set_data_logging(visualizer.data_logging_class)

        worker_thread = QtCore.QThread()
        worker        = BOSWorker(frame, bos_estimator)
        worker.moveToThread(worker_thread)

        def on_worker_finished():
            loading_window.close()
            visualizer.show()
            if hasattr(bos_estimator, 'visualizer_2d') and bos_estimator.visualizer_2d is not None:
                bos_estimator.visualizer_2d.show()
            logger.info("Application initialisation completed")

        def on_worker_error(error_msg):
            loading_window.close()
            show_error_message(f"Initialisation failed: {error_msg}")
            app.quit()

        worker.finished.connect(on_worker_finished)
        worker.error.connect(on_worker_error)
        worker_thread.started.connect(worker.run)
        worker.finished.connect(worker_thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker_thread.finished.connect(worker_thread.deleteLater)
        worker_thread.start()

        def cleanup_and_exit():
            logger.info("Shutting down MOBBO application...")
            try:
                # Stop recording if active
                if (bos_estimator._data_logging is not None
                        and bos_estimator._data_logging.is_recording):
                    bos_estimator._data_logging.toggle_recording()

                bos_estimator.stop_all_threads()
                frame.stop()
                logger.info("Cleanup completed successfully")
            except Exception as e:
                logger.error(f"Cleanup error: {e}")

        app.aboutToQuit.connect(cleanup_and_exit)

        exit_code = app.exec_()
        logger.info(f"Application exited with code: {exit_code}")
        return exit_code

    except Exception as e:
        logger.critical(f"Critical startup error: {e}")
        show_error_message(f"Critical startup error: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
