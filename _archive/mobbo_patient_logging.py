"""
Patient-based CSV logging extension for MobboData
Adds CoP and Foot Keypoint logging to existing MobboData class
"""

import os
import csv
import time
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def add_patient_logging_to_mobbo(mobbo_instance):
    """
    Add patient logging methods to an existing MobboData instance.

    Args:
        mobbo_instance: MobboData instance from COP_wifi_data.py
    """
    # Initialize patient logging attributes
    mobbo_instance.patient_cop_csv_file = None
    mobbo_instance.patient_cop_csv_writer = None
    mobbo_instance.patient_foot_csv_file = None
    mobbo_instance.patient_foot_csv_writer = None
    mobbo_instance.patient_cop_csv_path = None
    mobbo_instance.patient_foot_csv_path = None
    mobbo_instance.patient_name = None

    def start_patient_logging(session_folder, patient_name):
        """
        Start logging CoP and foot keypoint data to CSV files.

        Args:
            session_folder: Path to session folder
            patient_name: Name of the patient for logging

        Returns:
            bool: True if successful, False otherwise
        """
        mobbo_instance.patient_name = patient_name

        try:
            # Create timestamp for this logging session
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Create CoP CSV file
            mobbo_instance.patient_cop_csv_path = os.path.join(
                session_folder,
                f"CoP_{timestamp}.csv"
            )
            mobbo_instance.patient_cop_csv_file = open(mobbo_instance.patient_cop_csv_path, mode='w', newline='')
            mobbo_instance.patient_cop_csv_writer = csv.writer(mobbo_instance.patient_cop_csv_file)
            # Write header
            mobbo_instance.patient_cop_csv_writer.writerow([
                'timestamp', 'epoch_time', 'gcop_x', 'gcop_y', 'gcop_z', 'gcop_weight'
            ])

            # Create foot keypoint CSV file
            mobbo_instance.patient_foot_csv_path = os.path.join(
                session_folder,
                f"FootKeypoints_{timestamp}.csv"
            )
            mobbo_instance.patient_foot_csv_file = open(mobbo_instance.patient_foot_csv_path, mode='w', newline='')
            mobbo_instance.patient_foot_csv_writer = csv.writer(mobbo_instance.patient_foot_csv_file)
            # Write header
            mobbo_instance.patient_foot_csv_writer.writerow([
                'timestamp', 'epoch_time', 'left_heel_x', 'left_heel_y', 'left_heel_z',
                'left_toe_x', 'left_toe_y', 'left_toe_z',
                'right_heel_x', 'right_heel_y', 'right_heel_z',
                'right_toe_x', 'right_toe_y', 'right_toe_z'
            ])

            logger.info(f"✅ Patient CoP CSV opened: {mobbo_instance.patient_cop_csv_path}")
            logger.info(f"✅ Patient Foot CSV opened: {mobbo_instance.patient_foot_csv_path}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to start patient logging: {e}")
            return False

    def stop_patient_logging():
        """Stop logging CoP and foot keypoint data and close files."""
        try:
            if mobbo_instance.patient_cop_csv_file:
                mobbo_instance.patient_cop_csv_file.close()
                mobbo_instance.patient_cop_csv_file = None
            if mobbo_instance.patient_foot_csv_file:
                mobbo_instance.patient_foot_csv_file.close()
                mobbo_instance.patient_foot_csv_file = None
            logger.info(f"✅ Patient logging stopped for: {mobbo_instance.patient_name}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to stop patient logging: {e}")
            return False

    def log_cop_data_to_csv(gcop_x, gcop_y, gcop_z, gcop_weight):
        """
        Log CoP data to CSV file.

        Args:
            gcop_x, gcop_y, gcop_z: Global CoP coordinates
            gcop_weight: CoP weight
        """
        if mobbo_instance.patient_cop_csv_writer:
            try:
                current_time = time.time()
                timestamp = datetime.fromtimestamp(current_time).isoformat()
                mobbo_instance.patient_cop_csv_writer.writerow([
                    timestamp, current_time, gcop_x, gcop_y, gcop_z, gcop_weight
                ])
                mobbo_instance.patient_cop_csv_file.flush()
            except Exception as e:
                logger.error(f"❌ Error logging CoP data: {e}")

    def log_foot_keypoints_to_csv(left_heel, left_toe, right_heel, right_toe):
        """
        Log foot keypoint data to CSV file.

        Args:
            left_heel, left_toe: (x, y, z) tuples for left foot
            right_heel, right_toe: (x, y, z) tuples for right foot
        """
        if mobbo_instance.patient_foot_csv_writer:
            try:
                current_time = time.time()
                timestamp = datetime.fromtimestamp(current_time).isoformat()
                row = [timestamp, current_time]

                # Add coordinates (handle None values)
                row.extend(left_heel if left_heel else [None, None, None])
                row.extend(left_toe if left_toe else [None, None, None])
                row.extend(right_heel if right_heel else [None, None, None])
                row.extend(right_toe if right_toe else [None, None, None])

                mobbo_instance.patient_foot_csv_writer.writerow(row)
                mobbo_instance.patient_foot_csv_file.flush()
            except Exception as e:
                logger.error(f"❌ Error logging foot keypoints: {e}")

    # Bind methods to instance
    mobbo_instance.start_patient_logging = start_patient_logging
    mobbo_instance.stop_patient_logging = stop_patient_logging
    mobbo_instance.log_cop_data_to_csv = log_cop_data_to_csv
    mobbo_instance.log_foot_keypoints_to_csv = log_foot_keypoints_to_csv

    logger.info("✅ Patient logging methods added to MobboData instance")
