"""
Godot Bridge Module
Sends Global Center of Pressure (GCoP) data to Godot game engine in real-time
Supports both JSON and binary float32 formats
"""

import socket
import json
import time
import threading
import logging
import struct
from typing import Optional, Callable
import numpy as np

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
        self.data_format = data_format  # "json" or "binary"

        # Create UDP socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Thread control
        self._running = False
        self._thread = None
        self._lock = threading.Lock()

        # Data callback (function to get latest Gcop)
        self._data_callback: Optional[Callable] = None

        # Statistics
        self.packets_sent = 0
        self.last_sent_time = 0
        self.connection_status = "Disconnected"

        logger.info(f"GodotBridge initialized - Target: {godot_ip}:{godot_port} (format: {data_format})")

    def set_data_callback(self, callback: Callable):
        """
        Set callback function to get Gcop data

        Args:
            callback: Function that returns (gcop_x, gcop_y, gcop_z, total_weight)
        """
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
                # Get data from callback
                if self._data_callback:
                    data = self._data_callback()
                    if data:
                        self._send_data(data)

                time.sleep(self.send_rate)

            except Exception as e:
                logger.error(f"Error in GodotBridge send loop: {e}")
                time.sleep(0.1)

    def _send_data(self, data: dict):
        """
        Send data packet to Godot

        Args:
            data: Dictionary containing gcop_x, gcop_y, gcop_z, weight, etc.
        """
        try:
            if self.data_format == "json":
                # JSON format (for new implementations)
                json_data = json.dumps(data)
                packet = json_data.encode('utf-8')

            else:  # binary format (for existing NOARK games)
                # Pack as float32 array: [message_code, x, y, z]
                # message_code: 2.0 = connected/sending data
                message_code = 2.0
                x = float(data.get('x', 0.0))
                y = float(data.get('y', 0.0))
                z = float(data.get('z', 0.0))

                # Pack as 4 float32 values (16 bytes total)
                packet = struct.pack('4f', message_code, x, y, z)

            # Send via UDP
            self.sock.sendto(packet, (self.godot_ip, self.godot_port))

            # Update statistics
            self.packets_sent += 1
            self.last_sent_time = time.time()

            # Log periodically (every 100 packets)
            if self.packets_sent % 100 == 0:
                logger.debug(f"Sent packet #{self.packets_sent} to Godot: {data}")

        except Exception as e:
            logger.error(f"Failed to send data to Godot: {e}")

    def send_single_packet(self, gcop_x: float, gcop_y: float, gcop_z: float = 0.0,
                          weight: float = 0.0, **kwargs):
        """
        Send a single data packet (useful for testing or manual control)

        Args:
            gcop_x: Global CoP X coordinate
            gcop_y: Global CoP Y coordinate
            gcop_z: Global CoP Z coordinate (default: 0)
            weight: Total weight on sensors
            **kwargs: Additional data to send
        """
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

"""
Updated GodotBridgeHelper with optimized board pose sending
Only sends board pose initially and when configuration changes
"""

class GodotBridgeHelper:
    """Helper class to integrate GodotBridge with BOSEstimator - DUAL UDP PORT VERSION"""

    def __init__(self, gcop_array, data_lock, godot_ip="127.0.0.1", godot_port=8000,
                 godot_port_camera=8001, data_format="json"):
        """
        Initialize helper with DUAL UDP ports

        Args:
            gcop_array: Reference to global gcop1 array
            data_lock: Threading lock for safe access
            godot_ip: Godot IP address
            godot_port: UDP port for high-frequency data (CoP, Board Pose) - default 8000
            godot_port_camera: UDP port for camera data (FBP, BoS) - default 8001
            data_format: "json" or "binary" (default: "json")
        """
        self.gcop_array = gcop_array
        self.data_lock = data_lock
        self.total_weight = 0.0

        # Store local CoPs and global CoP separately
        self.local_cops = []  # List of local CoP dictionaries
        self.gcop = None      # Global CoP dictionary

        # Store all other data types
        self.board_pose_data = None
        self.bos_data = None
        self.fbp_data = None

        # Board pose change tracking
        self.board_pose_sent = False
        self.previous_board_pose_hash = None
        self.send_board_pose_next = False

        # Create PRIMARY bridge for CoP + Board Pose (high frequency)
        self.bridge = GodotBridge(godot_ip, godot_port, data_format=data_format)
        self.bridge.set_data_callback(self._get_cop_data)

        # Create SECONDARY bridge for FBP + BoS (camera frequency)
        self.bridge_camera = GodotBridge(godot_ip, godot_port_camera, data_format=data_format, send_rate=0.033)
        self.bridge_camera.set_data_callback(self._get_camera_data)

        logger.info(f"🎮 Dual UDP Bridge initialized:")
        logger.info(f"   Port {godot_port}: CoP + Board Pose (high frequency)")
        logger.info(f"   Port {godot_port_camera}: FBP + BoS (camera frequency)")

    def _calculate_board_pose_hash(self, board_data: dict) -> int:
        """Calculate a hash of the board pose data to detect changes."""
        if not board_data:
            return 0
        
        boards = board_data.get('data', {}).get('boards', {})
        board_ids = tuple(sorted([int(bid) for bid in boards.keys()]))
        ref_id = board_data.get('data', {}).get('reference_id', -1)
        
        return hash((ref_id, board_ids))

    def _get_cop_data(self) -> Optional[dict]:
        """Callback for PRIMARY UDP port (8000) - CoP + Board Pose only"""
        try:
            with self.data_lock:
                data = {
                    "timestamp": time.time()
                }

                # Add CoP data (both local and global)
                if self.local_cops or self.gcop:
                    cop_data = {}

                    # Add local CoPs if available
                    if self.local_cops:
                        cop_data["local_cops"] = self.local_cops

                    # Add global CoP if available
                    if self.gcop:
                        cop_data["gcop"] = self.gcop

                    if cop_data:
                        data["cop"] = cop_data

                # Add Board Pose data ONLY if flagged to send
                if self.send_board_pose_next and self.board_pose_data:
                    data["board_pose"] = self.board_pose_data
                    self.send_board_pose_next = False
                    logger.info("📤 Sending board pose data to Godot (Port 8000)")

                # Only send if we have at least one type of data
                return data if len(data) > 1 else None

        except Exception as e:
            logger.error(f"Error getting CoP data: {e}")
        return None

    def _get_camera_data(self) -> Optional[dict]:
        """Callback for SECONDARY UDP port (8001) - FBP + BoS only"""
        try:
            with self.data_lock:
                data = {
                    "timestamp": time.time()
                }

                # Add BoS data if available
                if self.bos_data:
                    data["bos"] = self.bos_data

                # Add FBP data if available
                if self.fbp_data:
                    data["fbp"] = self.fbp_data

                # Only send if we have at least one type of data
                return data if len(data) > 1 else None

        except Exception as e:
            logger.error(f"Error getting camera data: {e}")
        return None

    def update_cop_data(self, local_cops: list, gcop: dict, total_weight: float):
        """
        Update CoP data for transmission (both local and global)
        
        Args:
            local_cops: List of local CoP dictionaries [{'x': ..., 'y': ..., 'z': ..., 'weight': ...}, ...]
            gcop: Global CoP dictionary {'x': ..., 'y': ..., 'z': ..., 'weight': ...}
            total_weight: Total weight across all sensors
        """
        with self.data_lock:
            self.local_cops = local_cops if local_cops else []
            self.gcop = gcop if gcop else None
            self.total_weight = total_weight
    
    def update_Boardpose_data(self, board_xyz):
        """
        Update Board pose data for transmission.
        Only flags for sending if:
        1. First time (never sent before)
        2. Board configuration changed
        """
        new_board_data = {
            "type": "board_pose",
            "data": board_xyz
        }
        new_hash = self._calculate_board_pose_hash(new_board_data)
        
        should_send = False
        
        if not self.board_pose_sent:
            should_send = True
            logger.info("🆕 First board pose data - flagging for send")
        elif new_hash != self.previous_board_pose_hash:
            should_send = True
            logger.info("🔄 Board configuration changed - flagging for send")
        
        if should_send:
            self.board_pose_data = new_board_data
            self.send_board_pose_next = True
            self.previous_board_pose_hash = new_hash
            self.board_pose_sent = True
    
    def update_BoS_data(self, BOS_XYZ):
        """Update BOS data for transmission"""
        self.bos_data = {
            "type": "bos",
            "data": BOS_XYZ
        }
    
    def update_FBP_data(self, FBP_XYZ):
        """Update FBP data for transmission"""
        self.fbp_data = {
            "type": "fbp",
            "data": FBP_XYZ
        }

    def start(self):
        """Start sending to Godot on BOTH UDP ports"""
        self.bridge.start()  # Port 8000: CoP + Board Pose
        self.bridge_camera.start()  # Port 8001: FBP + BoS
        logger.info("✅ GodotBridgeHelper started (Dual UDP)")
        logger.info("   Port 8000: Sending CoP + Board Pose")
        logger.info("   Port 8001: Sending FBP + BoS")

    def stop(self):
        """Stop sending to Godot on BOTH UDP ports"""
        self.bridge.stop()
        self.bridge_camera.stop()
        logger.info("🛑 GodotBridgeHelper stopped (both ports)")

    def get_status(self):
        """Get status"""
        status = self.bridge.get_status()
        status['board_pose_sent'] = self.board_pose_sent
        status['board_pose_hash'] = self.previous_board_pose_hash
        status['local_cops_count'] = len(self.local_cops)
        status['has_gcop'] = self.gcop is not None
        return status


if __name__ == "__main__":
    """Test the Godot Bridge"""
    logging.basicConfig(level=logging.INFO)

    # Create test bridge
    bridge = GodotBridge(godot_ip="127.0.0.1", godot_port=8000)

    # Test sending data
    print("Starting Godot Bridge test...")
    bridge.start()

    # Simulate sending CoP data for 5 seconds
    for i in range(50):
        # Simulate CoP movement in a circle
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
