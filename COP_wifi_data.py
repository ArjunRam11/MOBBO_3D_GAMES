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
from board_pose_json_recorder import BoardPoseJSONRecorder
import logging
import json

logger = logging.getLogger(__name__)

stop_flag_wifi2 = True
record_start    = False
is_recording    = None
csv_files       = {}
csv_writers     = {}
board_save      = False
foot_point_save = False

_mobbo_instance = None


class MobboData:
    def __init__(self):
        self.local_ip  = Ip()
        self.foot_recorder = FootDataRecorder()

        self.UDP_IP   = self.local_ip.Local_ip()[0]
        self.UDP_PORT = 23000
        self.MESSAGE  = "Hey!mobbos"

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 4)
        self.sock.settimeout(2)

        self.missed_data_count = 0
        self.cop_data          = {}
        self.board_position    = None
        self.board_save        = False
        self.left_points       = None
        self.right_points      = None

        self._message_counters = {}
        self.data_types        = {"cop": True, "bos": True, "angles": True}

        # ── Paths owned by SessionManager — set when recording starts ──────
        self._cop_trial_path   = None   # CoP_Data/trialN/   (CSVs go here directly)
        self._foot_trial_path  = None   # Foot_Data/trialN/
        self._board_data_path  = None   # Board_Data/        (Board_Poses.json)
        self._patient_name     = None
        self._json_recorder    = None

    # ─────────────────────────────────────────────────────────────────────────
    # CoP CSV recording
    # ─────────────────────────────────────────────────────────────────────────

    def start_recording(self, addr):
        """Open a CSV file for this board address inside the current trial folder."""
        global csv_files, csv_writers

        if not self._cop_trial_path:
            logger.warning(f"⚠️  CoP trial path not set — cannot record for {addr}")
            return

        filename = os.path.join(
            self._cop_trial_path,
            f"data_{addr[0]}.csv"
        )

        csv_file   = open(filename, mode='w', newline='')
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(["time", "f1", "f2", "f3", "f4", "COPx", "COPy", "W", "W_sync"])
        csv_files[addr]   = csv_file
        csv_writers[addr] = csv_writer

        logger.info(f"📊 CoP CSV opened: {filename}")

    def stop_recording(self, addr):
        global csv_files
        if addr in csv_files:
            csv_files[addr].close()
            del csv_files[addr]
            del csv_writers[addr]

    # ─────────────────────────────────────────────────────────────────────────
    # Recording state — called from DataLogging
    # ─────────────────────────────────────────────────────────────────────────

    def set_recording_state(self, state: bool, cop_trial_path: str,
                            patient_name: str = None,
                            board_data_folder: str = None,
                            foot_trial_path: str = None):
        """
        Start or stop recording.

        Args:
            state            : True = start, False = stop
            cop_trial_path   : Absolute path to CoP_Data/trialN/  (CSVs go here)
            patient_name     : Patient ID (for JSON metadata)
            board_data_folder: Absolute path to Board_Data/ (Board_Poses.json lives here)
            foot_trial_path  : Absolute path to Foot_Data/trialN/ (optional)
        """
        global is_recording, board_save, foot_point_save

        is_recording = state

        if state:
            # ── Paths ──────────────────────────────────────────────────────
            self._cop_trial_path  = cop_trial_path
            self._foot_trial_path = foot_trial_path
            self._board_data_path = board_data_folder
            self._patient_name    = patient_name or "unknown"

            # ── Initialize Board_Poses.json recorder ───────────────────────
            if board_data_folder:
                os.makedirs(board_data_folder, exist_ok=True)
                self._json_recorder = BoardPoseJSONRecorder(
                    patient_name=self._patient_name,
                    board_data_dir=board_data_folder   # direct path, no session logic
                )
                logger.info(f"✅ BoardPoseJSONRecorder ready: {board_data_folder}")
            else:
                logger.warning("⚠️  board_data_folder not provided — Board_Poses.json will not be saved")

            board_save      = True
            foot_point_save = True
            logger.info(f"▶️  Recording started → CoP: {cop_trial_path}")

        else:
            # ── Stop and close all open CSV files ──────────────────────────
            for addr in list(csv_files.keys()):
                self.stop_recording(addr)

            # ── Flush foot recorder ────────────────────────────────────────
            try:
                self.foot_recorder.stop()
            except Exception:
                pass

            board_save      = False
            foot_point_save = False
            self._json_recorder = None
            logger.info("⏹️  Recording stopped")

    # ─────────────────────────────────────────────────────────────────────────
    # Board pose JSON
    # ─────────────────────────────────────────────────────────────────────────

    def record_board_data(self):
        """Save current board pose to Board_Poses.json."""
        if not self.board_position:
            logger.warning("❌ No board position data to record")
            return
        if not self._json_recorder:
            logger.warning("❌ JSON recorder not initialized")
            return
        try:
            board_data_list = []
            for board_list in self.board_position:
                for data in board_list:
                    board_data_list.append(data)
            self._json_recorder.record_board_pose(board_data_list)
            logger.info("📊 Board pose recorded to JSON")
        except Exception as e:
            logger.error(f"❌ Board pose JSON failed: {e}", exc_info=True)

    # ─────────────────────────────────────────────────────────────────────────
    # Board / foot data setters
    # ─────────────────────────────────────────────────────────────────────────

    def set_board_data(self, board_position):
        self.board_position = board_position

    def set_foot_points(self, left_points, right_points):
        self.left_points  = left_points
        self.right_points = right_points

    # ─────────────────────────────────────────────────────────────────────────
    # WiFi data loop
    # ─────────────────────────────────────────────────────────────────────────

    def get_device_data(self):
        global stop_flag_wifi2, csv_writers, csv_files
        self.sock.sendto(self.MESSAGE.encode(), (self.UDP_IP, self.UDP_PORT))
        global is_recording, board_save, foot_point_save

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
                        t,f1, f2, f3, f4, copx, copy  = unpacked_data[4:]
                        w = f1+f2+f3+f4
                        w_sync = 0
                    else:
                        continue

                    self.cop_data[addr] = (copx, copy, w)
                    count = self._message_counters.get(addr, 0) + 1
                    self._message_counters[addr] = count

                    # Print raw CoP from each board (throttled: every 50 packets ≈ 0.5 s)
                    # if count % 50 == 0:
                    #     print(f"[WiFi] {addr[0]}  COPx={copx:+.2f}  COPy={copy:+.2f}  W={w:.2f}")
                    # sys.stdout.flush()

                    current_time = time.time()

                    if is_recording:
                        # Save board pose JSON once at start of recording
                        if board_save:
                            self.record_board_data()
                            board_save = False

                        # CoP CSV
                        if self.data_types.get("cop", False):
                            if addr not in csv_files:
                                self.start_recording(addr)
                            if addr in csv_writers:
                                csv_writers[addr].writerow(
                                    [current_time, f1, f2, f3, f4, copx, copy, w, w_sync]
                                )

                        # Foot data
                        if foot_point_save and self._foot_trial_path:
                            try:
                                self.foot_recorder.start(self._foot_trial_path)
                                foot_point_save = False
                            except Exception:
                                foot_point_save = False

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
            self.sock.close()

    def stop(self):
        global stop_flag_wifi2
        stop_flag_wifi2 = False

    def start(self):
        global stop_flag_wifi2
        stop_flag_wifi2 = True


# ── Singleton ─────────────────────────────────────────────────────────────────

def get_mobbo_instance() -> MobboData:
    global _mobbo_instance
    if _mobbo_instance is None:
        logger.info("🔧 Creating MobboData singleton...")
        _mobbo_instance = MobboData()
    return _mobbo_instance


def set_mobbo_instance(instance: MobboData):
    global _mobbo_instance
    _mobbo_instance = instance