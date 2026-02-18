import time
import socket
import struct
import os
import sys
import csv
import threading
import keyboard
from datetime import datetime
from local_ip_fetch import *
from foot_recorder import FootDataRecorder
from board_pose_json_recorder import BoardPoseJSONRecorder, initialize_recorder, set_board_layout, record_board_pose_global
import logging

logger = logging.getLogger(__name__)

stop_flag_wifi2 = True
record_start = False
is_recording=None
csv_files = {}
csv_writers = {}
board_save=False
foot_point_save=False
json_recorder = None  # Global JSON recorder instance for board poses

# IMPORTANT: Global singleton MobboData instance - use this instead of creating new instances
# This ensures all code (main.py, data threads, etc.) share the same instance
_mobbo_instance = None

class MobboData:
    def __init__(self):
        self.local_ip = Ip()

        self.foot_recorder = FootDataRecorder()

        self.UDP_IP = self.local_ip.Local_ip()[0]
        self.UDP_PORT = 23000
        self.MESSAGE = "Hey!mobbos"
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 4)
        self.sock.settimeout(2)
        self.missed_data_count = 0
        self.cop_data = {}
        self.board_position=None
        self.board_save=False

        self.left_points=None
        self.right_points=None

        # Message counter for reduced verbosity
        self._message_counters = {}

        # Data recording types
        self.data_types = {"cop": True, "bos": True, "angles": True}

        # Session and path tracking
        self.session_folder = None
        self.cop_data_folder = None
        self.current_recording_timestamp = None
        self.current_cop_csv_path = None

    def start_recording(self, addr):
        """Starts a new CSV file for recording data from a specific address."""

        global csv_files, csv_writers, record_start

        # Use session folder if available, otherwise fall back to path
        logger.debug(f"🔍 start_recording called: addr={addr}, cop_data_folder={self.cop_data_folder}")
        if not self.cop_data_folder:
            logger.warning(f"⚠️ CoP data folder not set, cannot start recording for {addr}")
            logger.warning(f"   self.cop_data_folder={self.cop_data_folder}")
            logger.warning(f"   self.session_folder={self.session_folder}")
            logger.warning(f"   json_recorder={json_recorder}")
            return

        # Create timestamp for this recording session if not already done
        if not self.current_recording_timestamp:
            self.current_recording_timestamp = datetime.now().strftime("%d%m%Y_%H%M%S")

        # Create filename with address and timestamp
        filename = os.path.join(
            self.cop_data_folder,
            f"data_{addr[0]}_{addr[1]}_{self.current_recording_timestamp}.csv"
        )

        # Store relative path for JSON reference (relative to session folder)
        relative_path = f"CoP_Data/data_{addr[0]}_{addr[1]}_{self.current_recording_timestamp}.csv"
        if addr == list(self.cop_data.keys())[0] if self.cop_data else False:
            # Store the first address's path
            self.current_cop_csv_path = relative_path

        csv_file = open(filename, mode='w', newline='')
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(["time", "f1", "f2", "f3", "f4", "COPx", "COPy", "W", "W_sync"])
        csv_files[addr] = csv_file
        csv_writers[addr] = csv_writer

        logger.info(f"📊 CoP CSV file opened: {filename}")


    def stop_recording(self, addr):
        """Stops recording data for a specific address."""
        global csv_files

        if addr in csv_files:
            csv_files[addr].close()
            del csv_files[addr]
            del csv_writers[addr]


    def get_device_data(self):

        global stop_flag_wifi2, csv_writers, csv_files
        self.sock.sendto(self.MESSAGE.encode(), (self.UDP_IP, self.UDP_PORT))
        global is_recording,board_save,path,foot_point_save
        try:
            while True:
                if keyboard.is_pressed('q'):

                    break
                if not stop_flag_wifi2:

                    break
                try:
                    data, addr = self.sock.recvfrom(2048)
                    if len(data) == 34:
                        unpacked_data = struct.unpack('4c7fh', data)
                        f1, f2, f3, f4, copx, copy, w, w_sync = unpacked_data[4:]
                    elif len(data) == 32:
                        unpacked_data = struct.unpack('4c7f', data)
                        f1, f2, f3, f4, copx, copy, w = unpacked_data[4:]
                        w_sync = 0
                    else:
                        continue
                    self.cop_data[addr] = (copx, copy, w)
                    # Reduced verbosity - only log every 50th message per address
                    self._message_counters[addr] = self._message_counters.get(addr, 0) + 1

                    # Only print every 50th message to reduce console spam
                    # if self._message_counters[addr] % 50 == 0:
                        # print(f"[{self._message_counters[addr]}] {addr}: COPx={copx:+.3f}, COPy={copy:+.3f}, W={w:+.3f}")

                    # For debugging, uncomment the line below
                    # print(f"Received data from {addr}: COPx={copx:+3.3f}, COPy={copy:+3.3f}, W={w:+3.3f}", end='\r')

                    sys.stdout.flush()
                    current_time = time.time()
                    if is_recording:
                        if board_save:
                            self.record_board_data()
                            board_save = False

                        # Only record CoP data if selected
                        if self.data_types.get("cop", False):
                            if addr not in csv_files:
                                self.start_recording(addr)

                        if foot_point_save:
                            # Use session_folder from JSON recorder (with patient/session structure)
                            # instead of old path variable
                            if self.session_folder:
                                self.foot_recorder.start(self.session_folder)
                                logger.info(f"📊 Foot data recording started in: {self.session_folder}")
                            else:
                                logger.warning("⚠️ Session folder not set, cannot start foot recording")
                            foot_point_save = False

                    elif addr in csv_files:
                        # for addr in list(csv_files.keys()):
                        self.stop_recording(addr)
                        self.foot_recorder.stop()

                    # Write CoP data to CSV if recording is enabled for this data type
                    if addr in csv_writers and self.data_types.get("cop", False):
                        csv_writers[addr].writerow([current_time, f1, f2, f3, f4, copx, copy, w, w_sync])



                    self.foot_recorder.record_frame(self.left_points, self.right_points)


                    self.missed_data_count = 0
                except socket.timeout:
                    self.missed_data_count += 1

                    if self.missed_data_count > 1:

                        self.sock.sendto(self.MESSAGE.encode(), (self.UDP_IP, self.UDP_PORT))
                        self.missed_data_count = 0  
                except KeyboardInterrupt:

                    break
        finally:
            # DISABLED: File closing operations
            # for addr in list(csv_files.keys()):
            #     self.stop_recording(addr)
            self.sock.close()


    def stop(self):
        """Stops data fetching."""
        global stop_flag_wifi2
        stop_flag_wifi2 = False


    def start(self):
        """Starts data fetching."""
        global stop_flag_wifi2
        stop_flag_wifi2 = True


    def record_board_data(self):
        """Record board data to JSON using the global JSON recorder."""
        global json_recorder

        # Check if board_position is valid
        if not self.board_position:
            logger.warning("❌ No board position data to record")
            return

        # Check if JSON recorder is initialized
        if not json_recorder:
            logger.warning("❌ JSON recorder not initialized")
            return

        try:
            # Flatten board position data if nested
            board_data_list = []
            for board_list in self.board_position:  # Unpack first-level list
                for data in board_list:  # Unpack second-level list
                    board_data_list.append(data)

            # Get current CSV file paths if available
            cop_csv_path = self.current_cop_csv_path
            foot_csv_path = None  # Will be set when foot data recording is available

            # Record to JSON with file path references
            json_file = json_recorder.record_board_pose(
                board_data_list,
                cop_csv_path=cop_csv_path,
                foot_csv_path=foot_csv_path
            )
            logger.info(f"📊 Board pose recorded to JSON: {json_file}")
            if cop_csv_path:
                logger.info(f"   CoP CSV path: {cop_csv_path}")

        except Exception as e:
            logger.error(f"❌ Failed to record board data to JSON: {e}", exc_info=True)



                
    
    def set_board_data(self,board_position):
        self.board_position=board_position
     
    def set_recording_state(self, state, trial_path, patient_name=None, data_types=None):
        """
        Update the recording state and initialize JSON recorder for board poses.

        Args:
            state: True to start recording, False to stop
            trial_path: Path where trial data should be saved
            patient_name: Name of the patient (used for folder organization)
            data_types: Dict with keys "cop", "bos", "angles" indicating which data types to record
        """
        global is_recording, path, board_save, foot_point_save, json_recorder

        logger.info(f"🔄 set_recording_state called: state={state}, patient_name='{patient_name}', trial_path='{trial_path}'")

        is_recording = state
        path = trial_path

        # Update data types if provided
        if data_types is not None:
            self.data_types = data_types.copy()

        if state:
            logger.info(f"📍 Starting recording: json_recorder is {'None' if json_recorder is None else 'already initialized'}")
            # Initialize JSON recorder for this trial (once per session)
            if json_recorder is None:
                logger.info(f"🔍 Initializing new JSON recorder...")
                # Use patient_name if provided, otherwise extract from trial_path
                if not patient_name:
                    # Try to extract patient name from trial path structure
                    # Expected format: Mobbo_data/[PATIENT_NAME]/session_... or similar
                    import os
                    path_parts = os.path.normpath(trial_path).split(os.sep)
                    patient_name = "unknown_patient"
                    if "Mobbo_data" in path_parts:
                        idx = path_parts.index("Mobbo_data")
                        if idx + 1 < len(path_parts):
                            patient_name = path_parts[idx + 1]
                    logger.info(f"🔍 Extracted patient name from path: '{patient_name}'")

                logger.info(f"🔍 Calling initialize_recorder({patient_name}, {trial_path})...")
                json_recorder = initialize_recorder(patient_name, trial_path)
                logger.info(f"✅ JSON recorder initialized for patient '{patient_name}' at: {trial_path}")

                # Get session folder and CoP data folder from recorder
                self.session_folder = json_recorder.get_session_folder()
                self.cop_data_folder = json_recorder.get_cop_data_dir()
                logger.info(f"✅ Session folder set: {self.session_folder}")
                logger.info(f"✅ CoP data folder: {self.cop_data_folder}")
                logger.info(f"✅ self.cop_data_folder is now: {self.cop_data_folder}")
            else:
                logger.warning(f"⚠️  JSON recorder already initialized, skipping re-initialization")

            # Reset recording timestamp for new recording session
            self.current_recording_timestamp = None
            self.current_cop_csv_path = None

            board_save = True
            foot_point_save = True
        else:
            # Reset flags when stopping recording
            board_save = False
            foot_point_save = False

            # Reset JSON recorder so a new one is created for next recording
            json_recorder = None
            logger.info("📋 JSON recorder reset for next session")

    def set_board_layout(self, layout_data):
        """
        Set board layout information to be included in the JSON file.

        Args:
            layout_data: Dict from analyze_board_layout() containing layout info
        """
        global json_recorder
        if json_recorder:
            json_recorder.set_board_layout(layout_data)
            logger.info(f"📐 Board layout set on JSON recorder: {layout_data.get('layout', 'unknown')}")
        else:
            logger.warning("⚠️ JSON recorder not initialized, cannot set layout")

    def set_foot_points(self,left_points,right_points):
        self.left_points=left_points
        self.right_points=right_points


# ============================================================
# SINGLETON MANAGEMENT - Ensure only one MobboData instance
# ============================================================

def get_mobbo_instance():
    """
    Get the global singleton MobboData instance.
    Creates it if it doesn't exist.

    Returns:
        MobboData: The singleton instance
    """
    global _mobbo_instance
    if _mobbo_instance is None:
        logger.info("🔧 Creating global MobboData singleton instance...")
        _mobbo_instance = MobboData()
        logger.info(f"✅ Global MobboData instance created: {_mobbo_instance}")
    return _mobbo_instance


def set_mobbo_instance(instance):
    """
    Set the global MobboData instance (for testing or external initialization).

    Args:
        instance: MobboData instance to use globally
    """
    global _mobbo_instance
    _mobbo_instance = instance
    logger.info(f"✅ Global MobboData instance set to: {instance}")


if __name__ == '__main__':
    mobbo = MobboData()
    thread = threading.Thread(target=mobbo.get_device_data)
    thread.start()
    
    path = r'D:\MOCAP\MOBBO_multiple_board_data_logging\Mobbo_data\ezhil\session4_19032025_100850\trial2'

    
     
    
    # time.sleep(2)
    # mobbo.set_recording_state(True, path)

    # time.sleep(10)
    # mobbo.set_recording_state(False, path)

    # time.sleep(2)
    # mobbo.set_recording_state(True, path)

    # time.sleep(5)
    # mobbo.set_recording_state(False, path)
    # time.sleep(2)
    # mobbo.set_recording_state(True,path)  # ✅ Start recording (creates CSV)
    
    # time.sleep(2)
    # mobbo.set_recording_state(False,path)  # ✅ Stop recording (closes CSV)

    # time.sleep(2)
    # mobbo.set_recording_state(True,path)  # ✅ Start recording again (creates NEW CSV)
    
    # time.sleep(2)
    # mobbo.set_recording_state(False,path)  # ✅ Stop recording

