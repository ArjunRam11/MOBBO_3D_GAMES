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

stop_flag_wifi2 = True
record_start = False
is_recording=None
csv_files = {}
csv_writers = {}
board_save=False
foot_point_save=False

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

        # # Create base folder for storing CSV files
        # base_path = os.getcwd()
        # self.cop_data_folder = os.path.join(base_path, "Cop_Data")
        # os.makedirs(self.cop_data_folder, exist_ok=True)

    def start_recording(self, addr):
        """Starts a new CSV file for recording data from a specific address."""


        global csv_files, csv_writers, record_start,path

        # Create base folder for storing CSV files
        base_path =path
        self.cop_data_folder = os.path.join(base_path, "Cop_Data")
        os.makedirs(self.cop_data_folder, exist_ok=True)
         
        date_time_str = datetime.now().strftime("%d%m%Y_%H%M%S")
        filename = os.path.join(self.cop_data_folder, f"data_{addr[0]}_{addr[1]}_{date_time_str}.csv")
        
        csv_file = open(filename, mode='w', newline='')
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(["time","f1", "f2", "f3", "f4", "COPx", "COPy", "W", "W_sync"])
        csv_files[addr] = csv_file
        csv_writers[addr] = csv_writer


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
                            self.foot_recorder.start(path)
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
            for addr in list(csv_files.keys()):
                self.stop_recording(addr)
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
        global path

        data_folder = os.path.join(path, "Board_Data")
        os.makedirs(data_folder, exist_ok=True)
        timestamp = datetime.now().strftime("%d%m%Y_%H%M%S")  
        csv_filename = os.path.join(data_folder, f"Board_Position_{timestamp}.csv")

        with open(csv_filename, mode='w', newline='') as file:
            writer = csv.writer(file)

            # Write header
            writer.writerow(["board_translation", "ip_address", "angle", "rotation_matrix", "board_aruco_ids"])

            # Check if board_position is valid
            if not self.board_position:

                return
            
          
            for board_list in self.board_position:  # Unpack first-level list
                for data in board_list:  # Unpack second-level list
                    writer.writerow([
                        data["board_translation"].flatten().tolist(),  # Convert numpy array to list
                        data["ip_address"].strip(),  # Remove any extra spaces
                        data["angle"],  # Tuple is fine
                        data["rotation_matrix"].flatten().tolist(),  # Convert numpy array to list
                        data["board_aruco_ids"].tolist()  # Convert numpy array to list
                    ])



                
    
    def set_board_data(self,board_position):
        self.board_position=board_position
     
    def set_recording_state(self, state, trial_path, data_types=None):
        """
        Update the recording state and create a new CSV file when resuming recording.

        Args:
            state: True to start recording, False to stop
            trial_path: Path where trial data should be saved
            data_types: Dict with keys "cop", "bos", "angles" indicating which data types to record
        """
        global is_recording, path, board_save, foot_point_save

        is_recording = state
        path = trial_path

        # Update data types if provided
        if data_types is not None:
            self.data_types = data_types.copy()

        if state:
            board_save = True
            foot_point_save = True
        else:
            # Reset flags when stopping recording
            board_save = False
            foot_point_save = False
        # self.record_board_data()

    def set_foot_points(self,left_points,right_points):
        self.left_points=left_points
        self.right_points=right_points

 
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

