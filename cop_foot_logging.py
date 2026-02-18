"""
Patient-Based CoP and Foot Keypoint Data Logging Module
Saves CoP and foot keypoint data organized by patient name
Similar structure to existing recording: Mobbo_data/[patient_name]/session[N]_DDMMYYYY_HHMMSS/
"""

import os
import csv
import threading
import logging
from datetime import datetime
from pathlib import Path
import time
from typing import Optional, Dict, List, Tuple

logger = logging.getLogger(__name__)


class PatientDataLogger:
    """Logs CoP and foot keypoint data organized by patient name"""

    def __init__(self, base_data_path: str = "Mobbo_data"):
        """
        Initialize the patient data logger

        Args:
            base_data_path: Base directory where patient folders will be created (default: Mobbo_data)
        """
        self.base_data_path = base_data_path
        self.current_patient_id = None
        self.patient_session_path = None
        self.is_logging = False

        # CSV file handles
        self.cop_csv_file = None
        self.cop_csv_writer = None
        self.foot_csv_file = None
        self.foot_csv_writer = None

        # Data buffer for CoP and foot keypoints
        self.cop_buffer = []
        self.foot_buffer = []

        # Thread safety
        self._lock = threading.Lock()
        self._flush_thread = None
        self._running = False

        # Logging metadata
        self.logging_start_time = None
        self.cop_log_path = None
        self.foot_log_path = None
        self.session_number = 1

        logger.info(f"📋 PatientDataLogger initialized with base path: {base_data_path}")

    def set_patient(self, patient_id: str) -> bool:
        """
        Set the current patient and create patient folder structure

        Args:
            patient_id: Patient ID/name from Godot (e.g., "effe", "Arjun")

        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            self.current_patient_id = patient_id

            # Determine session number for this patient/date
            patient_data_path = os.path.join(self.base_data_path, patient_id)
            self.session_number = self._get_next_session_number(patient_data_path)

            # Create patient folder structure: Mobbo_data/[patient_name]/session[N]_DDMMYYYY_HHMMSS/
            timestamp = datetime.now().strftime("%d%m%Y_%H%M%S")
            session_folder = f"session{self.session_number}_{timestamp}"

            self.patient_session_path = os.path.join(
                self.base_data_path,
                patient_id,
                session_folder
            )

            try:
                # Create directories if they don't exist
                os.makedirs(self.patient_session_path, exist_ok=True)
                logger.info(f"✅ Patient session folder created: {self.patient_session_path}")
                return True
            except Exception as e:
                logger.error(f"❌ Failed to create patient folder: {e}")
                return False

    def _get_next_session_number(self, patient_data_path: str) -> int:
        """
        Determine the next available session number for the patient

        Args:
            patient_data_path: Path to patient's data folder

        Returns:
            Next session number (1-based)
        """
        if not os.path.exists(patient_data_path):
            return 1

        session_numbers = []
        try:
            for folder in os.listdir(patient_data_path):
                if folder.startswith("session"):
                    # Extract session number from "session1_DDMMYYYY_HHMMSS"
                    parts = folder.split("_")
                    if len(parts) > 0:
                        try:
                            num = int(parts[0].replace("session", ""))
                            session_numbers.append(num)
                        except ValueError:
                            pass
        except Exception as e:
            logger.warning(f"⚠️ Error reading session folders: {e}")

        return max(session_numbers, default=0) + 1

    def start_logging(self) -> bool:
        """
        Start logging CoP and foot keypoint data

        Returns:
            True if logging started successfully, False otherwise
        """
        if not self.current_patient_id:
            logger.warning("⚠️ Cannot start logging: Patient not set")
            return False

        if self.is_logging:
            logger.warning("⚠️ Logging already in progress")
            return False

        with self._lock:
            try:
                # Create timestamp for this logging session
                self.logging_start_time = datetime.now()
                timestamp = self.logging_start_time.strftime("%Y%m%d_%H%M%S")

                # Create CoP CSV file
                self.cop_log_path = os.path.join(
                    self.patient_session_path,
                    f"CoP_{timestamp}.csv"
                )
                self.cop_csv_file = open(self.cop_log_path, mode='w', newline='')
                self.cop_csv_writer = csv.writer(self.cop_csv_file)
                # Write header
                self.cop_csv_writer.writerow([
                    'timestamp', 'epoch_time', 'gcop_x', 'gcop_y', 'gcop_z',
                    'gcop_weight', 'local_cops_count'
                ])

                # Create foot keypoint CSV file
                self.foot_log_path = os.path.join(
                    self.patient_session_path,
                    f"FootKeypoints_{timestamp}.csv"
                )
                self.foot_csv_file = open(self.foot_log_path, mode='w', newline='')
                self.foot_csv_writer = csv.writer(self.foot_csv_file)
                # Write header
                self.foot_csv_writer.writerow([
                    'timestamp', 'epoch_time', 'left_heel_x', 'left_heel_y', 'left_heel_z',
                    'left_toe_x', 'left_toe_y', 'left_toe_z',
                    'right_heel_x', 'right_heel_y', 'right_heel_z',
                    'right_toe_x', 'right_toe_y', 'right_toe_z'
                ])

                self.is_logging = True
                self._running = True

                # Start buffer flush thread
                self._flush_thread = threading.Thread(target=self._flush_buffer_loop, daemon=True)
                self._flush_thread.start()

                logger.info(f"✅ Data logging STARTED for patient: {self.current_patient_id}")
                logger.info(f"   Session: {self.patient_session_path}")
                logger.info(f"   CoP data: {self.cop_log_path}")
                logger.info(f"   Foot data: {self.foot_log_path}")
                return True

            except Exception as e:
                logger.error(f"❌ Failed to start logging: {e}")
                self.is_logging = False
                return False

    def stop_logging(self) -> bool:
        """
        Stop logging and close files

        Returns:
            True if logging stopped successfully, False otherwise
        """
        if not self.is_logging:
            logger.warning("⚠️ Logging not in progress")
            return False

        with self._lock:
            try:
                self._running = False

                # Flush remaining data
                self._flush_cop_buffer()
                self._flush_foot_buffer()

                # Close files
                if self.cop_csv_file:
                    self.cop_csv_file.close()
                    self.cop_csv_file = None

                if self.foot_csv_file:
                    self.foot_csv_file.close()
                    self.foot_csv_file = None

                self.is_logging = False

                # Calculate duration
                if self.logging_start_time:
                    duration = datetime.now() - self.logging_start_time
                    logger.info(f"✅ Data logging STOPPED for patient: {self.current_patient_id}")
                    logger.info(f"   Duration: {duration}")

                return True

            except Exception as e:
                logger.error(f"❌ Failed to stop logging: {e}")
                return False

    def log_cop_data(self, gcop: Dict, local_cops: List[Dict], epoch_time: float = None):
        """
        Log center of pressure data

        Args:
            gcop: Global CoP dictionary with x, y, z, weight keys
            local_cops: List of local CoP dictionaries
            epoch_time: Unix timestamp (auto-generated if not provided)
        """
        if not self.is_logging:
            return

        if epoch_time is None:
            epoch_time = time.time()

        timestamp = datetime.fromtimestamp(epoch_time).isoformat()

        with self._lock:
            try:
                # Log global CoP
                if gcop:
                    self.cop_buffer.append([
                        timestamp,
                        epoch_time,
                        gcop.get('x', 0.0),
                        gcop.get('y', 0.0),
                        gcop.get('z', 0.0),
                        gcop.get('weight', 0.0),
                        len(local_cops) if local_cops else 0
                    ])
            except Exception as e:
                logger.error(f"❌ Error logging CoP data: {e}")

    def log_foot_keypoints(self, left_heel: Tuple, left_toe: Tuple,
                          right_heel: Tuple, right_toe: Tuple,
                          epoch_time: float = None):
        """
        Log foot keypoint data

        Args:
            left_heel: (x, y, z) tuple for left heel
            left_toe: (x, y, z) tuple for left toe
            right_heel: (x, y, z) tuple for right heel
            right_toe: (x, y, z) tuple for right toe
            epoch_time: Unix timestamp (auto-generated if not provided)
        """
        if not self.is_logging:
            return

        if epoch_time is None:
            epoch_time = time.time()

        timestamp = datetime.fromtimestamp(epoch_time).isoformat()

        with self._lock:
            try:
                row = [timestamp, epoch_time]

                # Add left heel
                row.extend(left_heel if left_heel else [None, None, None])

                # Add left toe
                row.extend(left_toe if left_toe else [None, None, None])

                # Add right heel
                row.extend(right_heel if right_heel else [None, None, None])

                # Add right toe
                row.extend(right_toe if right_toe else [None, None, None])

                self.foot_buffer.append(row)
            except Exception as e:
                logger.error(f"❌ Error logging foot keypoints: {e}")

    def _flush_buffer_loop(self):
        """Periodically flush buffers to CSV files"""
        while self._running:
            try:
                time.sleep(1.0)  # Flush every 1 second
                self._flush_cop_buffer()
                self._flush_foot_buffer()
            except Exception as e:
                logger.error(f"❌ Error in flush loop: {e}")

    def _flush_cop_buffer(self):
        """Flush CoP buffer to CSV"""
        with self._lock:
            if self.cop_buffer and self.cop_csv_writer and self.cop_csv_file:
                try:
                    self.cop_csv_writer.writerows(self.cop_buffer)
                    self.cop_csv_file.flush()
                    self.cop_buffer = []
                except Exception as e:
                    logger.error(f"❌ Error flushing CoP buffer: {e}")

    def _flush_foot_buffer(self):
        """Flush foot buffer to CSV"""
        with self._lock:
            if self.foot_buffer and self.foot_csv_writer and self.foot_csv_file:
                try:
                    self.foot_csv_writer.writerows(self.foot_buffer)
                    self.foot_csv_file.flush()
                    self.foot_buffer = []
                except Exception as e:
                    logger.error(f"❌ Error flushing foot buffer: {e}")

    def get_logging_status(self) -> Dict:
        """Get current logging status"""
        return {
            'is_logging': self.is_logging,
            'current_patient': self.current_patient_id,
            'cop_file': self.cop_log_path,
            'foot_file': self.foot_log_path,
            'buffered_cop_records': len(self.cop_buffer),
            'buffered_foot_records': len(self.foot_buffer),
            'logging_duration': (datetime.now() - self.logging_start_time).total_seconds() if self.logging_start_time else 0
        }


# Global singleton instance
_logger_instance: Optional[PatientDataLogger] = None


def get_patient_logger() -> PatientDataLogger:
    """Get or create the global patient logger instance"""
    global _logger_instance
    if _logger_instance is None:
        # Determine base path - use NOARKGames relative to current directory
        noark_path = os.path.join(os.path.dirname(__file__), "../NOARKGames")
        base_path = os.path.join(noark_path, "Mobbo_data")
        _logger_instance = PatientDataLogger(base_path)
    return _logger_instance


def initialize_patient_logger(base_path: str = None) -> PatientDataLogger:
    """Initialize the patient logger with custom base path"""
    global _logger_instance
    if base_path is None:
        # Default to Mobbo_data
        noark_path = os.path.join(os.path.dirname(__file__), "../NOARKGames")
        base_path = os.path.join(noark_path, "Mobbo_data")
    _logger_instance = PatientDataLogger(base_path)
    return _logger_instance
