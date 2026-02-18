"""
Godot Bridge Module - FIXED VERSION with Atomic Replacements
Sends Global Center of Pressure (GCoP) data to Godot game engine in real-time
Supports both JSON and binary float32 formats
NO MORE IN-PLACE MODIFICATIONS - Uses atomic reference replacement
FIXED VERSION - Working CoP/GCoP/FBP with Reset Command Support
"""

import socket
import json
import time
import threading
import logging
import struct
import copy
from typing import Optional, Callable
import numpy as np
from cop_foot_logging import get_patient_logger

logger = logging.getLogger(__name__)


class GodotBridge:
    """Bridge class to send CoP data to Godot game engine via UDP"""

    def __init__(self, godot_ip: str = "127.0.0.1", godot_port: int = 8000,
                 send_rate: float = 0.02, data_format: str = "binary"):
        """
        Initialize Godot Bridge

        Args:
            godot_ip: IP address where Godot is running (default: localhost)
            godot_port: UDP port for Godot to receive data (default: 8000)
            send_rate: Time interval between sends in seconds (default: 0.02 = 50Hz)
            data_format: "json" or "binary" (default: "binary" for existing NOARK games)
        """
        self.godot_ip = godot_ip
        self.godot_port = godot_port
        self.send_rate = send_rate
        self.data_format = data_format

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # CRITICAL FIX: Set socket to non-blocking to prevent deadlock on second reset
        # This prevents sendto() from blocking if Godot's socket buffer is full
        self.sock.setblocking(False)

        self._running = False
        self._thread = None
        self._lock = threading.Lock()

        self._data_callback: Optional[Callable] = None

        self.packets_sent = 0
        self.last_sent_time = 0
        self.connection_status = "Disconnected"

        logger.info(f"GodotBridge initialized - Target: {godot_ip}:{godot_port} (format: {data_format})")

    def set_data_callback(self, callback: Callable):
        """Set callback function to get Gcop data"""
        with self._lock:
            self._data_callback = callback

    def start(self):
        """Start sending data to Godot"""
        if self._running:
            logger.warning("GodotBridge already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self._send_loop, daemon=True)
        self._thread.start()
        self.connection_status = "Connected"
        logger.info("GodotBridge started")

    def stop(self):
        """Stop sending data to Godot"""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self.connection_status = "Disconnected"
        logger.info(f"GodotBridge stopped - Total packets sent: {self.packets_sent}")

    def _send_loop(self):
        """Main loop for sending data to Godot"""
        while self._running:
            try:
                if self._data_callback:
                    data = self._data_callback()
                    if data:
                        self._send_data(data)

                time.sleep(self.send_rate)

            except Exception as e:
                logger.error(f"Error in GodotBridge send loop: {e}")
                time.sleep(0.1)

    def _send_data(self, data: dict):
        """Send data packet to Godot"""
        try:
            if self.data_format == "json":
                json_data = json.dumps(data)
                packet = json_data.encode('utf-8')

            else:  # binary format
                message_code = 2.0
                x = float(data.get('x', 0.0))
                y = float(data.get('y', 0.0))
                z = float(data.get('z', 0.0))

                packet = struct.pack('4f', message_code, x, y, z)

            self.sock.sendto(packet, (self.godot_ip, self.godot_port))

            self.packets_sent += 1
            self.last_sent_time = time.time()

            if self.packets_sent % 100 == 0:
                logger.debug(f"Sent packet #{self.packets_sent} to Godot: {data}")

        except (BlockingIOError, OSError) as e:
            # Non-blocking socket would raise BlockingIOError if buffer full
            # This is OK - skip this packet and continue, Godot will get next one
            if self.packets_sent % 500 == 0:
                logger.debug(f"Socket buffer full, skipping packet: {e}")
        except Exception as e:
            logger.error(f"Failed to send data to Godot: {e}")

    def send_single_packet(self, gcop_x: float, gcop_y: float, gcop_z: float = 0.0,
                          weight: float = 0.0, **kwargs):
        """Send a single data packet"""
        data = {
            "type": "gcop",
            "x": float(gcop_x),
            "y": float(gcop_y),
            "z": float(gcop_z),
            "weight": float(weight),
            "timestamp": time.time(),
            **kwargs
        }
        self._send_data(data)

    def get_status(self) -> dict:
        """Get bridge status information"""
        return {
            "running": self._running,
            "connection_status": self.connection_status,
            "godot_ip": self.godot_ip,
            "godot_port": self.godot_port,
            "packets_sent": self.packets_sent,
            "send_rate": self.send_rate,
            "last_sent": time.time() - self.last_sent_time if self.last_sent_time > 0 else None
        }

    def __del__(self):
        """Cleanup on deletion"""
        self.stop()
        self.sock.close()


class GodotBridgeHelper:
    """
    FIXED Helper class - Uses ATOMIC REPLACEMENTS instead of in-place modifications
    This prevents race conditions with Godot reading data mid-modification
    """

    def __init__(self, gcop_array, data_lock, godot_ip="127.0.0.1", godot_port=8000,
                 godot_port_camera=8001, data_format="json"):
        """Initialize helper with DUAL UDP ports"""
        self.gcop_array = gcop_array
        self.data_lock = data_lock
        self.total_weight = 0.0

        # CRITICAL: Initialize as IMMUTABLE empty objects (will be replaced, not modified)
        self.local_cops = []
        self.gcop = {}
        self.board_pose_data = {}

        # FIXED: Use flat arrays instead of nested dicts (Option A)
        self.fbp_points = [None] * 18      # Array of 18 individual keypoints
        self.bos_left_points = []          # Dynamic array for left foot points
        self.bos_right_points = []         # Dynamic array for right foot points

        # Legacy attributes for backward compatibility (deprecated)
        self.bos_data = {}
        self.fbp_data = {}

        self.board_pose_sent = False
        self.previous_board_pose_hash = None
        self.send_board_pose_next = False

        # Create PRIMARY bridge for CoP + Board Pose
        self.bridge = GodotBridge(godot_ip, godot_port, data_format=data_format, send_rate=0.005)
        self.bridge.set_data_callback(self._get_cop_data)

        # DISABLED: Secondary bridge for FBP + BoS - Only sending CoP + Board Pose
        # self.bridge_camera = GodotBridge(godot_ip, godot_port_camera, data_format=data_format, send_rate=0.008)
        # self.bridge_camera.set_data_callback(self._get_camera_data)
        self.bridge_camera = None  # Explicitly disable secondary bridge

        self.network_manager = type('NetworkManager', (), {})()
        self.network_manager.reset_board_requested = False
        self.network_manager.control_command = {}
        self.network_manager.recording_command = {}

        # Initialize patient data logger
        self.patient_logger = get_patient_logger()
        self.current_patient_id = None

        logger.info(f"🎮 Godot Bridge initialized (ATOMIC MODE):")
        logger.info(f"   Port {godot_port}: CoP + Board Pose (LOCAL CoP, GCoP, Board Pose)")
        logger.info(f"   FBP and BoS disabled - only sending CoP and Board Pose data")
        logger.info(f"   📋 Patient Data Logger initialized")

    def _calculate_board_pose_hash(self, board_data: dict) -> int:
        """Calculate hash of board pose data"""
        if not board_data:
            return 0
        
        if "data" in board_data:
            boards = board_data.get('data', {}).get('boards', {})
            ref_id = board_data.get('data', {}).get('reference_id', -1)
        else:
            boards = board_data.get('boards', {})
            ref_id = board_data.get('reference_id', -1)
        
        board_ids = tuple(sorted([int(bid) for bid in boards.keys()]))
        
        return hash((ref_id, board_ids))

    def _get_cop_data(self) -> Optional[dict]:
        """Callback for PRIMARY UDP port (8000) - Local CoP + GCoP + Board Pose"""
        try:
            with self.data_lock:
                data = {
                    "timestamp": time.time()
                }

                # ATOMIC READ: Get immutable references
                if self.local_cops or self.gcop:
                    cop_data = {}

                    if self.local_cops:
                        cop_data["local_cops"] = self.local_cops

                    if self.gcop:
                        cop_data["gcop"] = self.gcop

                    if cop_data:
                        data["cop"] = cop_data

                if self.send_board_pose_next and self.board_pose_data:
                    if isinstance(self.board_pose_data, dict) and "data" in self.board_pose_data:
                        data["board_pose"] = self.board_pose_data["data"]
                    else:
                        data["board_pose"] = self.board_pose_data

                    self.send_board_pose_next = False
                    logger.info("📤 Sending board pose data to Godot")

                # FIXED: Return data if it has EITHER cop data OR board_pose data
                # (not just when len > 1, which blocks board pose without CoP data)
                has_cop = "cop" in data
                has_board_pose = "board_pose" in data

                # Log CoP data if logging is active
                if has_cop:
                    self.log_cop_data_internal()

                return data if (has_cop or has_board_pose) else None

        except Exception as e:
            logger.error(f"Error getting CoP data: {e}")
        return None

    # DISABLED: _get_camera_data removed - Port 8001 disabled (FBP and BoS not sent)
    # def _get_camera_data(self) -> Optional[dict]:
    #     """Callback for SECONDARY UDP port - FBP + BoS (DISABLED)"""
    #     # ... function disabled ...

    def update_cop_data(self, local_cops: list, gcop: dict, total_weight: float):
        """
        Update CoP data - ATOMIC REPLACEMENT
        Creates new objects instead of modifying existing ones
        """
        with self.data_lock:
            # CRITICAL FIX: Replace entire reference atomically
            # Godot's old reference remains valid while we create new one
            self.local_cops = copy.deepcopy(local_cops) if local_cops else []
            self.gcop = copy.deepcopy(gcop) if gcop else {}
            self.total_weight = total_weight
    
    def update_Boardpose_data(self, board_xyz, force_send=False):
        """Update Board pose data - ATOMIC REPLACEMENT"""
        new_hash = self._calculate_board_pose_hash({"data": board_xyz} if "boards" in board_xyz else board_xyz)

        should_send = force_send

        if not force_send:
            if not self.board_pose_sent:
                should_send = True
                logger.info("🆕 First board pose data")
            elif new_hash != self.previous_board_pose_hash:
                should_send = True
                logger.info("🔄 Board configuration changed")

        if should_send:
            with self.data_lock:
                # CRITICAL FIX: Replace entire reference atomically
                self.board_pose_data = copy.deepcopy(board_xyz)
                self.send_board_pose_next = True
                self.previous_board_pose_hash = new_hash
                self.board_pose_sent = True
    
    def update_BoS_data(self, BOS_XYZ):
        """Update BOS data - ATOMIC REPLACEMENT"""
        with self.data_lock:
            # CRITICAL FIX: Replace entire reference atomically
            self.bos_data = copy.deepcopy(BOS_XYZ) if isinstance(BOS_XYZ, dict) else {}

    def update_FBP_data(self, FBP_XYZ):
        """Update FBP data - ATOMIC REPLACEMENT (DEPRECATED - use update_FBP_points_batch)"""
        with self.data_lock:
            # CRITICAL FIX: Replace entire reference atomically
            self.fbp_data = copy.deepcopy(FBP_XYZ) if isinstance(FBP_XYZ, dict) else {}

    def update_FBP_points_batch(self, keypoints_list):
        """
        Update all FBP points at once from a list (FIXED - Option A).

        Args:
            keypoints_list: List of dicts with {'x': float, 'y': float, 'z': float} or None
                           Should be 18 keypoints for MediaPipe
        """
        with self.data_lock:
            if keypoints_list:
                # Update each individual point atomically
                for i in range(min(len(keypoints_list), 18)):
                    kp = keypoints_list[i]
                    self.fbp_points[i] = copy.deepcopy(kp) if kp else None

                # Clear remaining slots
                for i in range(len(keypoints_list), 18):
                    self.fbp_points[i] = None
            else:
                # Clear all points
                self.fbp_points = [None] * 18

    def update_BoS_points(self, left_foot_list, right_foot_list):
        """
        Update BoS points as flat arrays (FIXED - Option A).

        Args:
            left_foot_list: List of [x, y, z] arrays for left foot polygon
            right_foot_list: List of [x, y, z] arrays for right foot polygon
        """
        with self.data_lock:
            self.bos_left_points = copy.deepcopy(left_foot_list) if left_foot_list else []
            self.bos_right_points = copy.deepcopy(right_foot_list) if right_foot_list else []

    def start(self):
        """Start sending to Godot on PRIMARY UDP port (8000 only)"""
        self.bridge.start()
        # DISABLED: Secondary bridge disabled - FBP/BoS not sent
        # if self.bridge_camera:
        #     self.bridge_camera.start()
        logger.info("✅ GodotBridgeHelper started (CoP + Board Pose only)")

    def stop(self):
        """Stop sending to Godot"""
        self.bridge.stop()
        # DISABLED: Secondary bridge disabled - FBP/BoS not sent
        # if self.bridge_camera:
        #     self.bridge_camera.stop()
        logger.info("🛑 GodotBridgeHelper stopped")

    def get_status(self):
        """Get status"""
        status = self.bridge.get_status()
        status['board_pose_sent'] = self.board_pose_sent
        status['board_pose_hash'] = self.previous_board_pose_hash
        status['local_cops_count'] = len(self.local_cops)
        status['has_gcop'] = bool(self.gcop)

        # Add patient logging status
        logger_status = self.patient_logger.get_logging_status()
        status['patient_logging'] = logger_status

        return status

    # ============ PATIENT DATA LOGGING METHODS ============

    def set_patient(self, patient_id: str) -> bool:
        """
        Set the current patient for data logging

        Args:
            patient_id: Patient ID/name from Godot (e.g., "effe", "Arjun")

        Returns:
            True if successful, False otherwise
        """
        self.current_patient_id = patient_id
        success = self.patient_logger.set_patient(patient_id)
        if success:
            logger.info(f"👤 Patient set to: {patient_id}")
        return success

    def start_patient_logging(self) -> bool:
        """
        Start logging CoP and foot keypoint data for current patient

        Returns:
            True if logging started successfully, False otherwise
        """
        if not self.current_patient_id:
            logger.warning("⚠️ Cannot start logging: Patient not set")
            return False

        success = self.patient_logger.start_logging()
        if success:
            logger.info(f"🔴 DATA LOGGING STARTED for patient: {self.current_patient_id}")
        return success

    def stop_patient_logging(self) -> bool:
        """
        Stop logging CoP and foot keypoint data

        Returns:
            True if logging stopped successfully, False otherwise
        """
        success = self.patient_logger.stop_logging()
        if success:
            logger.info(f"⚪ DATA LOGGING STOPPED for patient: {self.current_patient_id}")
        return success

    def log_cop_data_internal(self):
        """
        Log current CoP data to CSV (called from _get_cop_data)
        This logs the global CoP that's being sent to Godot
        """
        if self.patient_logger.is_logging and self.gcop:
            try:
                self.patient_logger.log_cop_data(
                    gcop=self.gcop,
                    local_cops=self.local_cops,
                    epoch_time=time.time()
                )
            except Exception as e:
                logger.error(f"❌ Error logging CoP data: {e}")

    def log_foot_keypoints_internal(self, left_heel: tuple, left_toe: tuple,
                                   right_heel: tuple, right_toe: tuple) -> bool:
        """
        Log foot keypoint data to CSV

        Args:
            left_heel: (x, y, z) tuple for left heel
            left_toe: (x, y, z) tuple for left toe
            right_heel: (x, y, z) tuple for right heel
            right_toe: (x, y, z) tuple for right toe

        Returns:
            True if logging was attempted, False otherwise
        """
        if self.patient_logger.is_logging:
            try:
                self.patient_logger.log_foot_keypoints(
                    left_heel=left_heel,
                    left_toe=left_toe,
                    right_heel=right_heel,
                    right_toe=right_toe,
                    epoch_time=time.time()
                )
                return True
            except Exception as e:
                logger.error(f"❌ Error logging foot keypoints: {e}")
                return False
        return False


if __name__ == "__main__":
    """Test the Godot Bridge"""
    logging.basicConfig(level=logging.INFO)

    bridge = GodotBridge(godot_ip="127.0.0.1", godot_port=8000)

    print("Starting Godot Bridge test...")
    bridge.start()

    for i in range(50):
        t = i * 0.1
        x = 0.1 * np.cos(t)
        y = 0.1 * np.sin(t)
        z = 0.0
        weight = 50.0 + 10 * np.sin(t)

        bridge.send_single_packet(x, y, z, weight)
        print(f"Sent packet {i+1}: x={x:.3f}, y={y:.3f}, weight={weight:.1f}")
        time.sleep(0.1)

    print("\nBridge Status:", bridge.get_status())
    bridge.stop()
    print("Test completed!")