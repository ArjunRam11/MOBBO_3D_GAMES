
#!/usr/bin/env python3
"""
Optimized MOBBO 3D Motion Analysis System

Main application for real-time biomechanical analysis combining:
- RealSense camera data
- ArUco board positioning
- Human pose estimation
- Foot keypoint detection
- Center of pressure calculation
"""

import sys
import time
import threading
import logging
import json
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from contextlib import contextmanager

import numpy as np
np.set_printoptions(precision=3, suppress=True)

import math
import cv2
from PyQt5 import QtWidgets, QtCore

# Specific imports instead of wildcards
from Graph_window_main import (
    ArUco3DVisualizer, data_lock, pose_3d_keypoints, gcop1, angles,
    left_heel_vector, left_toe_vector, right_heel_vector, right_toe_vector,
    MAT, DIST, pose, keypoints, varboard, referenceboard
)
from loading_process_widget import LoadingWindow, BOSWorker, ResetButtonProcess
from board_update_plot_graph import BoardMeshPlotter
from Frame_Process import Frame_Process
from board_pose_estimator import board_pose_estimator
from foot_process import foot_detector
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
from COP_wifi_data import MobboData
from godot_bridge import GodotBridgeHelper


def sanitize_fbp_data(keypoints_3d):
    """
    Sanitize FBP keypoints to ensure Godot-safe data
    
    Args:
        keypoints_3d: numpy array of shape (N, 3)
    
    Returns:
        List of lists with None for invalid values
    """
    if keypoints_3d is None:
        return None
    
    if isinstance(keypoints_3d, np.ndarray):
        # Check if all NaN
        if np.all(np.isnan(keypoints_3d)):
            return None
        
        sanitized = []
        for row in keypoints_3d:
            if len(row) >= 3:
                x = None if np.isnan(row[0]) else float(row[0])
                y = None if np.isnan(row[1]) else float(row[1])
                z = None if np.isnan(row[2]) else float(row[2])
                
                # Only add if at least one coordinate is valid
                if x is not None or y is not None or z is not None:
                    sanitized.append([x, y, z])
        
        # Need at least 3 valid keypoints
        return sanitized if len(sanitized) >= 3 else None
    
    return None
def sanitize_for_json(data):
    """
    Recursively sanitize data for JSON serialization by replacing NaN/inf values with None.
    Also filters out arrays/points that are entirely None/NaN.
    
    Args:
        data: Any data structure (dict, list, numpy array, scalar)
        
    Returns:
        Sanitized data structure safe for JSON serialization
    """
    if isinstance(data, dict):
        return {k: sanitize_for_json(v) for k, v in data.items()}
    
    elif isinstance(data, (list, tuple)):
        sanitized = [sanitize_for_json(item) for item in data]
        # Check if all elements are None
        if all(x is None for x in sanitized):
            return None
        return sanitized
    
    elif isinstance(data, np.ndarray):
        # Check if array contains all NaN/invalid values
        if np.all(np.isnan(data)) or data.size == 0:
            return None
        # Convert numpy array to list and sanitize each element
        return sanitize_for_json(data.tolist())
    
    elif isinstance(data, (np.floating, float)):
        # Replace NaN and inf with None
        if math.isnan(data) or math.isinf(data):
            return None
        return float(data)
    
    elif isinstance(data, (np.integer, int)):
        return int(data)
    
    elif data is None:
        return None
    
    else:
        # For other types, try to return as-is
        return data


def validate_polygon_data(polygon_data):
    """
    Validate polygon data to ensure it has valid points.
    Returns None if polygon is invalid, otherwise returns cleaned data.
    
    Args:
        polygon_data: Array of [x, y, z] points
        
    Returns:
        Cleaned polygon data or None if invalid
    """
    if polygon_data is None:
        return None
    
    if isinstance(polygon_data, np.ndarray):
        # Check if array is empty or all NaN
        if polygon_data.size == 0 or np.all(np.isnan(polygon_data)):
            return None
        
        # Filter out rows with any NaN values
        valid_rows = []
        for row in polygon_data:
            if len(row) >= 3 and not np.isnan(row).any():
                valid_rows.append([float(row[0]), float(row[1]), float(row[2])])
        
        # Need at least 3 points for a valid polygon
        if len(valid_rows) < 3:
            return None
        
        return valid_rows
    
    return None
# Configuration constants
CONFIG = {
    'SLEEP_INTERVALS': {
        'BOS_LOOP': 0.008,  # Reduced from 0.01 for better responsiveness
        'ARUCO_LOOP': 0.005,  # Faster processing
        'BOARD_SETUP': 0.3,   # Reduced from 0.5
        'ERROR_RECOVERY': 0.1
    },
    'FOOT_PARAMS': {
        'LENGTH': 0.27, 'WIDTH': 0.07, 'TOE_WIDTH': 0.1, 'HEIGHT': 0.020
    },
    'ROTATION_180': np.array([[-1, 0, 0], [0, -1, 0], [0, 0, 1]], dtype=np.float32),
    'CAMERA_DIMS': (1280, 720)
}

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ThreadState:
    """Thread state management"""
    bos_running: bool = False
    aruco_running: bool = False
    stop_requested: bool = False


@dataclass
class BoardData:
    """Consolidated board data structure"""
    points_3d: Dict[int, np.ndarray] = field(default_factory=dict)
    translations: Dict[int, np.ndarray] = field(default_factory=dict)
    rotations: Dict[int, np.ndarray] = field(default_factory=dict)
    ip_addresses: Dict[int, str] = field(default_factory=dict)
    relative_translations: Dict[int, np.ndarray] = field(default_factory=dict)
    relative_rotations: Dict[int, np.ndarray] = field(default_factory=dict)
    reference_ip: Optional[str] = None
    reference_id: Optional[int] = None
    reference_translation: Optional[np.ndarray] = None
    reference_rotation: Optional[np.ndarray] = None


class BoardManager:
    """Manages ArUco board detection and coordinate transformations"""

    def __init__(self):
        self.board_pose_estimator = board_pose_estimator()
        self._lock = threading.RLock()

    def detect_and_setup_boards(self, frame) -> BoardData:
        """Detect boards and setup coordinate system"""
        try:
            board_pose_data = self.board_pose_estimator.board_pose(frame)
            if not board_pose_data:
                logger.warning("No board pose data detected")
                return BoardData()

            return self._process_board_data(board_pose_data)
        except Exception as e:
            logger.error(f"Board detection failed: {e}")
            return BoardData()

    def _process_board_data(self, board_pose_data: List) -> BoardData:
        """Process raw board data into structured format"""
        board_data = BoardData()

        # Extract data efficiently
        translations = []
        rotation_matrices = []
        ip_addresses = []
        ids = []

        for board_info in board_pose_data:
            data = board_info[0]
            translation = data['board_translation'].reshape(3, 1)
            rotation_matrix = data['rotation_matrix'].reshape(3, 3)
            board_address = data['ip_address']
            board_ids = data['board_aruco_ids'].flatten().tolist()

            ids.extend(board_ids)
            translations.append(translation)
            rotation_matrices.append(rotation_matrix)
            ip_addresses.append(board_address)

        # Find reference board (closest to camera)
        distances = [t[2, 0] for t in translations]
        ref_index = np.argmin(distances)

        board_data.reference_ip = ip_addresses[ref_index]
        board_data.reference_id = ids[ref_index]
        board_data.reference_translation = translations[ref_index]
        board_data.reference_rotation = cv2.Rodrigues(rotation_matrices[ref_index])[0]

        # Process all boards
        with self._lock:
            for i, (translation, rotation_matrix, ip_addr, board_id) in enumerate(
                zip(translations, rotation_matrices, ip_addresses, ids)
            ):
                board_data.ip_addresses[board_id] = ip_addr
                board_data.translations[board_id] = translation
                board_data.rotations[board_id] = rotation_matrix

                # Calculate 3D board points
                board_points_3d, _ = get_rectangle_corners_3d(
                    translation, cv2.Rodrigues(rotation_matrix)[0],
                    MAT, DIST, 0.6, 0.45
                )

                board_position = plot_rectangle_3d_points(
                    board_data.reference_translation, board_data.reference_rotation,
                    board_data.reference_translation, board_data.reference_rotation,
                    board_points_3d
                )
                board_data.points_3d[board_id] = board_position

                # Calculate relative transformations for non-reference boards
                if i != ref_index:
                    ref_rot_T = np.transpose(rotation_matrices[ref_index])
                    board_data.relative_rotations[board_id] = np.matmul(
                        ref_rot_T, rotation_matrix
                    )
                    board_data.relative_translations[board_id] = np.matmul(
                        ref_rot_T, (translation - board_data.reference_translation)
                    )

        return board_data


class CoordinateTransformer:
    """Handles 3D coordinate transformations and CoP calculations"""

    def __init__(self):
        self._rotation_180 = CONFIG['ROTATION_180']

    def transform_cop_data(self, mobbo_data, board_data: BoardData) -> Tuple[List, float]:
        """Transform CoP data to reference coordinate system"""
        if not mobbo_data.cop_data or len(mobbo_data.cop_data) < 2:
            return [], 0.0

        total_weighted_cop = np.zeros((3, 1), dtype=np.float32)
        total_weight = 0.0
        all_cops = []

        # Pre-normalize reference IP for comparison
        ref_ip_normalized = str(board_data.reference_ip).strip().lower()

        for addr, (copx, copy, weight) in mobbo_data.cop_data.items():
            cop = np.array([[copx], [copy], [0]], dtype=np.float32)

            # Apply 180-degree rotation and scale
            cop_transformed = np.matmul(self._rotation_180.T, cop) / 100.0

            board_ip_normalized = str(addr[0]).strip().lower()

            if board_ip_normalized != ref_ip_normalized:
                # Find board ID and apply relative transformation
                board_id = self._find_board_id_by_ip(
                    board_data.ip_addresses, board_ip_normalized
                )
                if board_id and board_id in board_data.relative_rotations:
                    cop_transformed = np.matmul(
                        board_data.relative_rotations[board_id], cop_transformed
                    )
                    cop_transformed += board_data.relative_translations[board_id]

            all_cops.append((cop_transformed, weight))
            total_weighted_cop += weight * cop_transformed
            total_weight += weight

        # Sort by weight (descending)
        all_cops.sort(key=lambda x: x[1], reverse=True)
        return all_cops, total_weight

    @staticmethod
    def _find_board_id_by_ip(ip_dict: Dict[int, str], target_ip: str) -> Optional[int]:
        """Find board ID by IP address"""
        for board_id, ip_addr in ip_dict.items():
            if str(ip_addr).strip().lower() == target_ip:
                return board_id
        return None


class ThreadManager:
    """Manages thread lifecycle and synchronization"""

    def __init__(self):
        self.state = ThreadState()
        self._threads = {}
        self._lock = threading.RLock()

    @contextmanager
    def thread_context(self, name: str):
        """Context manager for safe thread operations"""
        try:
            yield
        except Exception as e:
            logger.error(f"Thread {name} error: {e}")
        finally:
            with self._lock:
                if name in self._threads:
                    del self._threads[name]

    def start_thread(self, name: str, target, args=()) -> bool:
        """Start a managed thread"""
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
        """Stop all managed threads"""
        self.state.stop_requested = True

        with self._lock:
            for name, thread in self._threads.items():
                if thread.is_alive():
                    logger.info(f"Stopping thread: {name}")
                    try:
                        thread.join(timeout=2.0)
                        if thread.is_alive():
                            logger.warning(f"Thread {name} did not stop gracefully")
                    except Exception as e:
                        logger.error(f"Error stopping thread {name}: {e}")

            self._threads.clear()

        logger.info("All threads stopped")


class BOSEstimator:
    
    """Optimized Base of Support Estimator with improved architecture"""

    def __init__(self, frame: Frame_Process):
        self.frame = frame
        self.mobbo = MobboData()
        self.foot_detection_model = foot_detector()
        self.recorder = FootDataRecorder()

        # Use new specialized managers
        self.board_manager = BoardManager()
        self.coord_transformer = CoordinateTransformer()
        self.thread_manager = ThreadManager()

        # Board and coordinate data
        self.board_data = BoardData()
        self.board_pose_mesh_plotter = None

        # Visualizer reference - will be set later
        self.visualizer = None
        self.previous_board_pose_hash = None
        self.board_pose_sent = False

        # Foot processing data - pre-allocated for efficiency
        self.foot_vectors = {
            'left_heel': np.full((1, 3), np.nan, dtype=np.float32),
            'left_toe': np.full((1, 3), np.nan, dtype=np.float32),
            'right_heel': np.full((1, 3), np.nan, dtype=np.float32),
            'right_toe': np.full((1, 3), np.nan, dtype=np.float32)
        }
        self.foot_numpy_points = [None, None]
        self.foot_scatter_points = [None, None]

        # CoP processing data
        self.all_cops = []
        self.total_weight = 0.0

        # State tracking
        self._initialized = False
        self.counter = 0  # For board mesh plotter initialization

        # Legacy attributes for compatibility
        self.board_points_3d = {}
        self.reference_board_id = None
        self.left_foot_polygon_point = None
        self.right_foot_polygon_point = None
        self.board_pose = board_pose_estimator()  # Legacy board pose estimator

        # Legacy thread attributes for cleanup compatibility
        self.bos_thread = None
        self.bos_thread_running = False
        self.aruco_thread_ = None
        self.aruco_thread_running = True
        self.Cop_thread = None
        self.Cop_thread_running = True

        # Legacy lock attributes
        self.board_point_lock = threading.Lock()
        self.data_lock = threading.Lock()

        # Godot Bridge for sending CoP data to game engine
        # Godot Bridge for sending CoP data to game engine
        self.godot_bridge = GodotBridgeHelper(
            gcop_array=gcop1,
            data_lock=data_lock,
            godot_ip="127.0.0.1",
            godot_port=8000,
            data_format="json"    # Changed from "binary" to "json"
        )

        # ============================================================
        # COMMAND SOCKET FOR GODOT RESET COMMANDS (UDP PORT 9000)
        # ============================================================
        self._command_socket = None
        self._init_command_socket()

        logger.info("BOSEstimator initialized with optimized architecture")

    def set_visualizer(self, visualizer):
        """Set the visualizer reference after initialization"""
        self.visualizer = visualizer

    def _init_command_socket(self):
        """Initialize UDP socket for receiving Godot commands on port 9000"""
        try:
            import socket
            self._command_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._command_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._command_socket.bind(("127.0.0.1", 9000))
            self._command_socket.settimeout(0.1)  # Non-blocking with 100ms timeout
            logger.info("📡 Command receiver listening on UDP port 9000")
            print("✅ SUCCESS: Command receiver listening on UDP port 9000")
        except Exception as e:
            logger.error(f"Failed to initialize command socket: {e}")
            print(f"❌ ERROR: Failed to initialize command socket: {e}")
            self._command_socket = None

    def stop_all_threads(self):

         global stop_flag_aruco ,stop_threads,process_complete
         stop_flag_aruco = False
         stop_threads=False
         process_complete=False
         with data_lock:
            varboard[0]=[""]
            referenceboard[0]=[" "]

         # Stop Godot bridge
         self.godot_bridge.stop()
         logger.info("Godot bridge stopped")

         self.foot_detection_model.foot_prediction_stopthread()

         # ============================================================
         # FIXED: Use timeout + check if called from within thread
         # ============================================================
         if self.bos_thread_running and self.bos_thread is not None:
             try:
                 # Check if we're being called FROM the BOS thread itself
                 # If so, skip join (thread can't join itself)
                 if threading.current_thread() != self.bos_thread:
                     # Wait max 2 seconds for thread to finish
                     self.bos_thread.join(timeout=2.0)
                     print("✅ BOS thread stopped cleanly")
                 else:
                     # Called from within the BOS thread (during reset)
                     # Just set flag - thread will exit naturally when it sees the stop flags
                     print("✅ BOS thread stop initiated (called from within thread)")
                 self.bos_thread_running = False
             except Exception as e:
                 print(f"⚠️ Error stopping BOS thread: {e}")
                 self.bos_thread_running = False


    def reset_all_threads(self):
        """Restart BOS processing: Re-detect boards and restart compute_COP thread."""
        try:
            # Step 1: Re-detect board positions (with NEW reference frame)
            print("🔍 Re-detecting board positions...")
            self.board_pose_detected_set(self.frame)
            print("✅ New board positions detected")

            # Step 2: Signal that board pose has CHANGED (force send to Godot)
            print("📡 Signaling board pose change to Godot...")
            self.godot_bridge.send_board_pose_next = True
            print("✅ Board pose change flag set")

            # Step 3: Restart the continuous compute_COP thread
            print("▶️ Restarting compute_COP thread...")
            # CRITICAL: Force flag to False before creating new thread
            # (even though stop_all_threads() should have done this)
            self.bos_thread_running = False
            time.sleep(0.1)  # Give old thread extra time to exit

            # Now create and start the new thread
            self.bos_thread = threading.Thread(target=self.compute_COP)
            self.bos_thread.start()
            self.bos_thread_running = True
            print("✅ compute_COP thread restarted successfully")

        except Exception as e:
            print(f"❌ Error during reset_all_threads: {e}")
            import traceback
            traceback.print_exc()

    def thread_process_all(self,frame):
        global process_complete

        if not self.bos_thread_running :
            self.bos_thread = threading.Thread(target=self.compute_COP)
            self.bos_thread.start()
            self.bos_thread_running=True
            logger.info("BOS thread started")

            # Start Godot bridge when BOS processing starts
            # print("=" * 60)
            # print("🎮 STARTING GODOT BRIDGE - Port 8000")
            # print("=" * 60)
            self.godot_bridge.start()
            logger.info("Godot bridge started - sending data to game")
            # print("✅ Godot bridge started successfully!")
            # print("=" * 60)

        self.aruco_thread_ = threading.Thread(target=self.run_aruco, args=(self.visualizer,1280, 720, MAT, DIST,frame))
        self.aruco_thread_.start()

        process_complete=True
        logger.info("All processing threads started")

  
    
 
    def board_pose_detected_set(self, frame):
        
        frame1 = frame
        board_pose_data = self.board_pose.board_pose(frame1)
        self.board_position_data=board_pose_data
        self.mobbo.set_board_data(self.board_position_data)
        # print(board_pose_data)
        time.sleep(0.5)

        self.board_points_3d = {}
        self.board_translations = {}
        self.board_rotations = {}
        self.board_ip = {}
        self.relative_translations = {}
        self.relative_rotations = {}
        self.ip_addresses = []
        self.reference_board_ip = None
        self.reference_board_id=None

        translations = []
        rotation_matrices = []
        ip_addresses = []
        ids = []
        self.board_points_3d = {}

        for i in range(len(board_pose_data)):
            translation = board_pose_data[i][0]['board_translation'].reshape(3, 1)
            rotation_matrix = board_pose_data[i][0]['rotation_matrix'].reshape(3, 3)
            board_address = board_pose_data[i][0]['ip_address']
            boards_ids = board_pose_data[i][0]['board_aruco_ids'].flatten().tolist()
            ids.extend(boards_ids)
            translations.append(translation)
            rotation_matrices.append(rotation_matrix)
            ip_addresses.append(board_address)


        distances = [t[2, 0] for t in translations]
        ref_index = np.argmin(distances)  # Closest board as reference
        self.reference_board_ip = ip_addresses[ref_index]
        self.reference_board_id=ids[ref_index]

        with self.board_point_lock:
            self.board_points_3d.clear()
            
            self.board_translations.clear()
            self.board_rotations.clear()
            self.relative_translations.clear()
            self.relative_rotations.clear()
            self.reference_board_translation=None
            self.reference_board_rotation=None

            for i in range(len(translations)):
                board_ids = ids[i]
                self.board_ip[board_ids] = ip_addresses[i]
                self.board_translations[board_ids] = translations[i]
                self.board_rotations[board_ids] = rotation_matrices[i]

                board_points_3d, _ = get_rectangle_corners_3d(
                    translations[i], cv2.Rodrigues(rotation_matrices[i])[0], MAT, DIST, 0.6, 0.45
                )

                board_position_find_realtime = plot_rectangle_3d_points(translations[ref_index], cv2.Rodrigues(rotation_matrices[ref_index])[0],
                                                                        translations[ref_index], cv2.Rodrigues(rotation_matrices[ref_index])[0], board_points_3d)
                self.board_points_3d[board_ids] = board_position_find_realtime

                if i != ref_index:
                    relative_rotation = np.matmul(
                        np.transpose(rotation_matrices[ref_index]), rotation_matrices[i]
                    )
                    relative_translation = np.matmul(
                        np.transpose(rotation_matrices[ref_index]),
                        (translations[i] - translations[ref_index])
                    )
                    self.relative_rotations[board_ids] = relative_rotation
                    self.relative_translations[board_ids] = relative_translation
            

            self.reference_board_translation=translations[ref_index]
            self.reference_board_rotation=cv2.Rodrigues(rotation_matrices[ref_index])[0]

            if self.counter==0 and self.visualizer:
                self.board_pose_mesh_update_graph = BoardMeshPlotter(self.visualizer.view)
                self.counter += 1

            if hasattr(self, 'board_pose_mesh_update_graph'):
                self.board_pose_mesh_update_graph.update_boards(self.board_points_3d, self.reference_board_id)


            board_xyz_data = {
            'reference_id': int(self.reference_board_id),
            'boards': {}}

            board_xyz_data['boards'][str(self.reference_board_id)] = {
            'id': int(self.reference_board_id),
            'relative_rotation_matrix': np.eye(3).flatten().tolist(),  # Identity matrix
            'relative_translation': [0.0, 0.0, 0.0]}  # Zero translation 
            print(self.relative_rotations)

            # Add relative pose data for each non-reference board
            for board_id in self.relative_rotations.keys():
                board_xyz_data['boards'][str(board_id)] = {
                    'id': int(board_id),
                    'relative_rotation_matrix': self.relative_rotations[board_id].flatten().tolist(),
                    'relative_translation': self.relative_translations[board_id].flatten().tolist()
                }

        # Send to Godot Bridge
        self.godot_bridge.update_Boardpose_data(board_xyz_data)

        self.previous_board_pose_hash = self._calculate_board_pose_hash(board_xyz_data)
        self.board_pose_sent = True
      

        global stop_flag_aruco, stop_threads
        stop_flag_aruco = True
        stop_threads = True
        
        self.thread_process_all(frame1)
    def _calculate_board_pose_hash(self, board_data: dict) -> int:
        """
        Calculate a hash of the board pose data to detect changes.
        Only considers reference_id and board IDs (not precise positions).
        """
        # Create a tuple of board IDs sorted for consistent hashing
        board_ids = tuple(sorted([int(bid) for bid in board_data['boards'].keys()]))
        ref_id = board_data['reference_id']
        
        # Hash based on which boards are present and which is reference
        return hash((ref_id, board_ids))

    def _has_board_configuration_changed(self, current_board_data: dict) -> bool:
        """
        Check if the board configuration has changed significantly.
        Returns True if boards were added/removed or reference changed.
        """
        if self.previous_board_pose_hash is None:
            return True
        
        current_hash = self._calculate_board_pose_hash(current_board_data)
        return current_hash != self.previous_board_pose_hash

    def compute_COP(self):
        global stop_flag_aruco, stop_threads

        while stop_threads and stop_flag_aruco:
            # ============================================================
            # CHECK FOR RESET COMMAND FROM GODOT VIA UDP PORT 9000
            # ============================================================
            if self._command_socket:
                try:
                    # Try to receive command (non-blocking)
                    data, addr = self._command_socket.recvfrom(1024)
                    if data:
                        try:
                            command_str = data.decode('utf-8')
                            command = json.loads(command_str)

                            if command.get('type') == 'reset_board' and command.get('action') == 'stop_all_threads':
                                print("\n📨 Reset board command received from Godot!")
                                print("🔴 Stopping all threads...")

                                try:
                                    # Stop all threads (with timeout protection)
                                    self.stop_all_threads()

                                    print("⏳ Waiting 1 second for graceful shutdown...")
                                    time.sleep(1)

                                    print("🟢 Restarting board detection...")
                                    self.reset_all_threads()

                                    print("✅ Board reset complete!\n")

                                    # CRITICAL: Break out of the loop so this thread can exit
                                    # and the new thread from reset_all_threads() can take over
                                    break

                                except Exception as e:
                                    print(f"❌ Error during reset sequence: {e}")
                                    print("⚠️ Reset may be incomplete, but continuing...")
                                    self.bos_thread_running = False
                                    break

                        except (json.JSONDecodeError, UnicodeDecodeError) as e:
                            logger.warning(f"Invalid command format: {e}")

                except Exception as e:
                    # Socket timeout is expected - just continue
                    if "timed out" not in str(e).lower():
                        logger.warning(f"Error receiving command: {e}")

            if self.mobbo.cop_data:
                addr_keys = list(self.mobbo.cop_data.keys())

                if len(addr_keys) >= 2:
                    total_weighted_cop = np.zeros((3, 1))
                    total_weight = 0
                    self.all_cops = []   

                    # Iterate through all available CoPs
                    for addr in addr_keys:
                        copx, copy, w = self.mobbo.cop_data[addr]
                        weight = w
                        cop = np.array([copx, copy, 0]).reshape(3, 1)

                        # Apply 180-degree rotation
                        rotation_180_n = np.array([[-1, 0, 0], [0, -1, 0], [0, 0, 1]])
                        cop_transformed = np.matmul(rotation_180_n.T, cop) / 100  

                        board_ip = str(addr[0]).strip().lower()
                        self.reference_board_ip = str(self.reference_board_ip).strip().lower()

                        if board_ip == self.reference_board_ip:  
                            # This is the reference board
                            self.all_cops.append((cop_transformed, w))
                        else:  
                            # This is NOT the reference board → Apply additional transformations
                            board_id_get = next((k for k, v in self.board_ip.items() 
                                            if str(v).strip().lower() == board_ip), None)

                            if board_id_get and board_id_get in self.relative_rotations:
                                cop_transformed = np.matmul(
                                    self.relative_rotations[board_id_get], cop_transformed
                                )
                                cop_transformed += self.relative_translations[board_id_get]

                            self.all_cops.append((cop_transformed, w))

                        # Compute total weighted CoP
                        total_weighted_cop += w * cop_transformed
                        total_weight += w

                    # Sort CoPs by weight (descending order)
                    self.all_cops.sort(key=lambda x: x[1], reverse=True)
                    
                    # Compute final global CoP
                    Gcop = total_weighted_cop / total_weight if total_weight != 0 else np.zeros((3, 1))
                    
                    # Update visualizer
                    if self.visualizer:
                        self.visualizer.cop_and_gcop_update(self.all_cops, total_weight)
                    
                    # Update shared data under lock
                    with data_lock:
                        if gcop1 is not None:
                            gcop1[:] = Gcop.flatten()

                    # ============================================================
                    # SEND LOCAL CoPs AND GLOBAL CoP TO GODOT BRIDGE
                    # ============================================================
                    
                    # Prepare local CoPs data (sanitized)
                    local_cops_data = []
                    for cop_vec, cop_weight in self.all_cops:
                        cop_flat = cop_vec.flatten()
                        local_cop = {
                            'x': sanitize_for_json(cop_flat[0]),
                            'y': sanitize_for_json(cop_flat[1]),
                            'z': sanitize_for_json(cop_flat[2]),
                            'weight': sanitize_for_json(cop_weight)
                        }
                        # Only add if not all None
                        if not all(v is None for v in local_cop.values()):
                            local_cops_data.append(local_cop)
                    
                    # Prepare global CoP data (sanitized)
                    gcop_flat = Gcop.flatten()
                    gcop_data = {
                        'x': sanitize_for_json(gcop_flat[0]),
                        'y': sanitize_for_json(gcop_flat[1]),
                        'z': sanitize_for_json(gcop_flat[2]),
                        'weight': sanitize_for_json(total_weight)
                    }
                    
                    # Send to Godot Bridge
                    self.godot_bridge.update_cop_data(
                        local_cops=local_cops_data,
                        gcop=gcop_data,
                        total_weight=total_weight
                    )

                    # ============================================================
                    # DEBUG: Verify CoP data is being sent
                    # ============================================================
                    # if not hasattr(self, '_send_counter'):
                    #     self._send_counter = 0
                    # self._send_counter += 1

                    # if self._send_counter % 100 == 0:
                    #     print(f"📤 PYTHON->GODOT CoP Packet #{self._send_counter}:")
                    #     print(f"   Local CoPs: {len(local_cops_data)}")
                    #     if len(local_cops_data) > 0:
                    #         lc = local_cops_data[0]
                    #         print(f"   Local[0]: x={lc['x']:.4f if lc['x'] else 'None'}, "
                    #               f"y={lc['y']:.4f if lc['y'] else 'None'}, "
                    #               f"w={lc['weight']:.2f if lc['weight'] else 'None'}")
                    #     print(f"   GCoP: x={gcop_data['x']:.4f if gcop_data['x'] else 'None'}, "
                    #           f"y={gcop_data['y']:.4f if gcop_data['y'] else 'None'}, "
                    #           f"z={gcop_data['z']:.4f if gcop_data['z'] else 'None'}, "
                    #           f"W={total_weight:.2f}")

            time.sleep(0.01)

        self.bos_thread_running = False


   
    def foot_shape_get_numpy_and_scatter_points(self, foot_keys, right_heel, 
                                                right_toe, left_heel, left_toe):
        """
        Generate foot polygon points and send BoS data to Godot bridge
        """
        self.left_foot_polygon_point = None
        self.right_foot_polygon_point = None
        
        self.foot_numpy_points = [None, None]
        self.foot_scatter_points = [None, None]

        if foot_keys:
            from matplotlib.path import Path
            
            # Process right foot
            if not np.isnan(right_heel).any() and not np.isnan(right_toe).any():
                self.right_foot_polygon_point, right_foot = create_foot_polygon_3d(
                    right_toe, right_heel, 0.27, 0.07, 0.1, 0.020, is_left=False
                )
                self.foot_numpy_points[0] = right_foot
                self.foot_scatter_points[0] = [right_heel, right_toe]
            
            # Process left foot
            if not np.isnan(left_heel).any() and not np.isnan(left_toe).any():
                self.left_foot_polygon_point, left_foot = create_foot_polygon_3d(
                    left_toe, left_heel, 0.27, 0.07, 0.1, 0.020, is_left=True
                )
                self.foot_numpy_points[1] = left_foot
                self.foot_scatter_points[1] = [left_heel, left_toe]

            # Set foot points in MOBBO data
            self.mobbo.set_foot_points(
                self.foot_numpy_points[1],
                self.foot_numpy_points[0]
            )

            # ============================================================
            # SEND BoS DATA TO GODOT BRIDGE WITH ENHANCED VALIDATION
            # ============================================================
            # Validate and clean polygon data before sending
            left_foot_clean = validate_polygon_data(self.foot_numpy_points[1])
            right_foot_clean = validate_polygon_data(self.foot_numpy_points[0])
            
            bos_data = {
                'left_foot': left_foot_clean,  # Already validated, will be None if invalid
                'right_foot': right_foot_clean  # Already validated, will be None if invalid
            }
            
            # Only send if at least one foot is valid
            if left_foot_clean is not None or right_foot_clean is not None:
                self.godot_bridge.update_BoS_data(bos_data)
                # Optional: Add debug counter if needed
                # if not hasattr(self, '_bos_send_counter'):
                #     self._bos_send_counter = 0
                # self._bos_send_counter += 1
                # if self._bos_send_counter % 100 == 0:
                #     print(f"📤 BoS #{self._bos_send_counter}: Left={left_foot_clean is not None}, Right={right_foot_clean is not None}")
            
    def run_aruco(self, visualizer, w, h, mat, dist, frame):
        """
        Modified run_aruco with board pose change detection
        """
        frame2 = frame
        
        ref_rotation_matrix = self.reference_board_rotation
        ref_translation = self.reference_board_translation

        self.foot_detection_model.start_detection(frame2)
        
        global stop_flag_aruco, stop_threads
        
        # Counter for periodic board checking
        board_check_counter = 0
        BOARD_CHECK_INTERVAL = 500  # Check every 500 frames (~every 5 seconds at 100fps)
        
        while stop_threads and stop_flag_aruco:
            left_heel_vector_ = np.full_like(left_heel_vector, np.nan)
            left_toe_vector_ = np.full_like(left_toe_vector, np.nan)
            right_heel_vector_ = np.full_like(right_heel_vector, np.nan)
            right_toe_vector_ = np.full_like(right_toe_vector, np.nan)
            
            foot_keys, depth_frame1, image1 = self.foot_detection_model.get_keypoints()

            # ============================================================
            # PERIODIC BOARD CONFIGURATION CHECK
            # ============================================================
            board_check_counter += 1
            if board_check_counter >= BOARD_CHECK_INTERVAL:
                board_check_counter = 0
                
                # Check if board configuration changed
                if self.board_pose_sent:
                    # Rebuild current board data
                    current_board_data = {
                        'reference_id': int(self.reference_board_id),
                        'boards': {}
                    }
                    current_board_data['boards'][str(self.reference_board_id)] = {
                        'id': int(self.reference_board_id),
                        'relative_rotation_matrix': np.eye(3).flatten().tolist(),
                        'relative_translation': [0.0, 0.0, 0.0]
                    }
                    for board_id in self.relative_rotations.keys():
                        current_board_data['boards'][str(board_id)] = {
                            'id': int(board_id),
                            'relative_rotation_matrix': self.relative_rotations[board_id].flatten().tolist(),
                            'relative_translation': self.relative_translations[board_id].flatten().tolist()
                        }
                    
                    # Check if changed
                    if self._has_board_configuration_changed(current_board_data):
                        # print("🔄 Board configuration changed - resending data")
                        self.godot_bridge.update_Boardpose_data(current_board_data)
                        self.previous_board_pose_hash = self._calculate_board_pose_hash(current_board_data)
                        # print("✅ Updated board pose data sent to Godot")

            # ============================================================
            # REST OF THE FOOT AND BODY PROCESSING (unchanged)
            # ============================================================
            if foot_keys is not None:
                def get_3d_point(key):
                    return (
                        get_any_3d_points(foot_keys[key][0], foot_keys[key][1], depth_frame1, MAT)
                        if key in foot_keys
                        else None
                    )
                
                right_top_3d = get_3d_point('right_top')
                right_bottom_3d = get_3d_point('right_bottom')
                left_top_3d = get_3d_point('left_top')
                left_bottom_3d = get_3d_point('left_bottom')

                with self.board_point_lock:
                    board_data = self.board_points_3d

                    if not board_data:
                        # print("Error: No board points data available!")
                        pass
                    else:
                        foot_start = True

                        if foot_start:
                            if left_top_3d is not None and left_bottom_3d is not None:
                                if np.any(left_top_3d) and np.any(left_bottom_3d):
                                    left_heel_vector_ = return_BOS_vectors_singlekeypoint_pyqt(
                                        ref_translation, ref_rotation_matrix, 
                                        ref_translation, ref_rotation_matrix, left_top_3d
                                    )
                                    left_toe_vector_ = return_BOS_vectors_singlekeypoint_pyqt(
                                        ref_translation, ref_rotation_matrix, 
                                        ref_translation, ref_rotation_matrix, left_bottom_3d
                                    )

                        if foot_start:
                            if right_top_3d is not None and right_bottom_3d is not None:
                                if np.any(right_top_3d) and np.any(right_bottom_3d):
                                    right_heel_vector_ = return_BOS_vectors_singlekeypoint_pyqt(
                                        ref_translation, ref_rotation_matrix, 
                                        ref_translation, ref_rotation_matrix, right_top_3d
                                    )
                                    right_toe_vector_ = return_BOS_vectors_singlekeypoint_pyqt(
                                        ref_translation, ref_rotation_matrix, 
                                        ref_translation, ref_rotation_matrix, right_bottom_3d
                                    )

            self.foot_shape_get_numpy_and_scatter_points(
                foot_keys, right_heel_vector_, right_toe_vector_, 
                left_heel_vector_, left_toe_vector_
            )

            # Human keypoints processing (unchanged)
            key_bool = True
            try:
                if key_bool:
                    processed_frame = image1
                    results = pose.process(cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB))
                    
                    if results.pose_landmarks:
                        keypoints_3d_dict = get_keypoints_3d_sealibrary(
                            results.pose_landmarks.landmark, depth_frame1, MAT
                        )
                        keypoints_matrix = np.array([
                            keypoints_3d_dict[k] if keypoints_3d_dict[k] is not None 
                            else [None, None, None] for k in keypoints_3d_dict.keys()
                        ])
                        corrected_keypoints = update_buffer(keypoints_matrix)

                        keypoints_from_ref_board = return_BOS_vectors_singlekeypoint(
                            ref_translation, ref_rotation_matrix,
                            ref_translation, ref_rotation_matrix, corrected_keypoints
                        )
                        # print(keypoints_from_ref_board)

                        with data_lock:
                            pose_3d_keypoints[:] = keypoints_from_ref_board

                        keypoint_angle = get_all_angles_from_18x3(keypoints_matrix)
                        keypoint_angle = np.array(keypoint_angle).reshape((8, 1))
                        
                        with data_lock:
                            angles[:] = keypoint_angle

                        # fbp_data = {
                        #     'keypoints_3d': keypoints_from_ref_board.tolist(),
                        #     'angles': keypoint_angle.flatten().tolist(),
                        #     'timestamp': time.time()
                        # }
                        fbp_data = {
                                'keypoints_3d': sanitize_fbp_data(keypoints_from_ref_board),
                            }
                        
                       # Only send if valid
                        if fbp_data['keypoints_3d'] is not None:
                            self.godot_bridge.update_FBP_data(fbp_data)

                        desired_keypoints = [
                            'head', 'neck', 'right_shoulder', 'left_shoulder',
                            'right_elbow', 'left_elbow', 'right_hand', 'left_hand',
                            'right_hip', 'left_hip', 'right_knee', 'left_knee',
                            'right_foot', 'left_foot', 'left_heel', 'right_heel',
                            'left_foot_index', 'right_foot_index'
                        ]
                        
                        if results.pose_landmarks:
                            for key in desired_keypoints:
                                landmark_index = keypoints[key]
                                landmark = results.pose_landmarks.landmark[landmark_index]
                                cx = int(landmark.x * image1.shape[1])
                                cy = int(landmark.y * image1.shape[0])
                                cv2.circle(image1, (cx, cy), 2, (0, 255, 0), cv2.FILLED)
                    else:
                        keypoints_from_ref_board = np.full((18, 3), np.nan)
                        with data_lock:
                            pose_3d_keypoints[:] = keypoints_from_ref_board

                    if image1 is not None:
                        if self.visualizer:
                            self.visualizer.camera_update(image1)

            except Exception as e:
                pass

            # Small sleep to prevent excessive CPU usage
            time.sleep(0.001)

            
def show_error_message(error_message: str):
    """Display an error message with proper logging and user feedback"""
    logger.error(f"Application error: {error_message}")

    try:
        error_dialog = QtWidgets.QMessageBox()
        error_dialog.setIcon(QtWidgets.QMessageBox.Critical)
        error_dialog.setWindowTitle("MOBBO Error")
        error_dialog.setText("An error occurred during processing:")
        error_dialog.setInformativeText(error_message)
        error_dialog.setDetailedText(f"Check logs for more details. Time: {time.strftime('%H:%M:%S')}")
        error_dialog.setStandardButtons(QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Retry)
        error_dialog.exec_()
    except Exception as e:
        logger.critical(f"Failed to show error dialog: {e}")
        print(f"CRITICAL ERROR: {error_message}")


def main():
    """Optimized main application entry point"""
    # Setup application
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("MOBBO 3D Motion Analysis")
    app.setApplicationVersion("2.0 Optimized")

    logger.info("Starting MOBBO application...")

    try:
        # Create and show loading window
        loading_window = LoadingWindow()
        loading_window.show()

        # Initialize core components with error checking
        frame = Frame_Process()
        if not frame.is_camera_connected():
            raise RuntimeError("No RealSense camera detected. Please connect camera and restart.")

        # Initialize optimized BOS estimator
        bos_estimator = BOSEstimator(frame)
        visualizer = ArUco3DVisualizer(bos_estimator)

        # Set visualizer reference in BOS estimator
        bos_estimator.set_visualizer(visualizer)

        # Create worker thread for initialization
        worker_thread = QtCore.QThread()
        worker = BOSWorker(frame, bos_estimator)
        worker.moveToThread(worker_thread)

        # Connect signals with error handling
        def on_worker_finished():
            loading_window.close()
            visualizer.show()
            logger.info("Application initialization completed")

        def on_worker_error(error_msg):
            loading_window.close()
            show_error_message(f"Initialization failed: {error_msg}")
            app.quit()

        worker.finished.connect(on_worker_finished)
        worker.error.connect(on_worker_error)
        worker_thread.started.connect(worker.run)
        worker.finished.connect(worker_thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker_thread.finished.connect(worker_thread.deleteLater)

        # Start worker thread
        worker_thread.start()

        # Setup graceful shutdown
        def cleanup_and_exit():
            logger.info("Shutting down application...")
            try:
                bos_estimator.stop_all_threads()
                frame.stop()
                logger.info("Cleanup completed successfully")
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")

        app.aboutToQuit.connect(cleanup_and_exit)

        # Run application
        exit_code = app.exec_()
        logger.info(f"Application exited with code: {exit_code}")
        return exit_code

    except Exception as e:
        logger.critical(f"Critical error during startup: {e}")
        show_error_message(f"Critical startup error: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

