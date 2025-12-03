import csv
import os
import numpy as np
from datetime import datetime
 
write_data=False
class FootDataRecorder:
    def __init__(self, folder="foot_data"):
        self.trial_path=None
        self.folder = None
        

        self.is_recording = False
        self.left_file = None
        self.right_file = None
        self.left_writer = None
        self.right_writer = None

        self.point_labels = [
            "heel_left", "heel_right", "metacarpal_right",
            "big_toe_point", "pinky_toe_point", "metacarpal_left"
        ]


    def _get_timestamped_filename(self, prefix):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return os.path.join( self.folder, f"{prefix}_foot_{timestamp}.csv")

    # def _write_header(self, writer):
    #     writer.writerow(["timestamp"] + self.point_labels)



    def _write_header(self, writer):
        label_row = ["timestamp"]
        axis_row = ["timestamp"]

        for label in self.point_labels:
            label_row.extend([label] * 3)
            axis_row.extend(["x", "y", "z"])

        writer.writerow(label_row)
        writer.writerow(axis_row)


    def start(self,trail_path):
        """Start a new recording session (creates new CSVs)"""
         
        self.folder= os.path.join(trail_path, "Foot_Data")
        os.makedirs(self.folder, exist_ok=True)
        self.is_recording = True

        self.left_file = open(self._get_timestamped_filename("left"), mode='w', newline='')
        self.right_file = open(self._get_timestamped_filename("right"), mode='w', newline='')

        self.left_writer = csv.writer(self.left_file)
        self.right_writer = csv.writer(self.right_file)

        self._write_header(self.left_writer)
        self._write_header(self.right_writer)

        global write_data
        write_data=True
 

    def stop(self):
        """Stop recording and close files"""
        global write_data
        write_data=False
        self.is_recording = False

        if self.left_file:
            self.left_file.close()
        if self.right_file:
            self.right_file.close()

        self.left_file = None
        self.right_file = None
        self.left_writer = None
        self.right_writer = None

        print("[Recorder] Stopped recording.")

    def _format_point_row(self, points):
        row = []
        for pt in points:
            if pt is not None and not np.isnan(pt).any():
                row.extend([f"{pt[0]:.5f}", f"{pt[1]:.5f}", f"{pt[2]:.5f}"])
            else:
                row.extend(["", "", ""])
        return row

    def record_frame(self, left_points , right_points ):
        
        """Call this repeatedly in your loop to store frames"""
        if not self.is_recording:
            return

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

        if self.left_writer and left_points is not None:
            row = [timestamp] + self._format_point_row(left_points)
            self.left_writer.writerow(row)

        if self.right_writer and right_points is not None:
            row = [timestamp] + self._format_point_row(right_points)
            self.right_writer.writerow(row)



        

