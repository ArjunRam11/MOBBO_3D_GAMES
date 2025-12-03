


import threading
import pyrealsense2 as rs
import numpy as np
import cv2
import copy
import time
from datetime import datetime
import os

class Frame_Process:
    def __init__(self):
        super().__init__()
        self.frames_lock = threading.Lock()
        self.color_frame = None
        self.depth_frame = None
        self.running = True  # Flag to indicate if the pipeline is running
        self.is_recording = False  # Flag to control recording state
        self.video_writer = None  # Video writer instance
        self.path = None
        self.fps = 30  # Frames per second for video
        self.video_width = 1280
        self.video_height = 720
        self.pipeline=None

    def is_camera_connected(self):
        """Check if a RealSense camera is connected."""
        context = rs.context()
        if len(context.devices) == 0:
            print("No RealSense camera detected.")
            return False
        return True

    def initialize_pipeline(self, width, height):
        self.pipeline = rs.pipeline()
        config = rs.config()
        config.enable_stream(rs.stream.color, width, height, rs.format.bgr8, self.fps)
        config.enable_stream(rs.stream.depth, width, height, rs.format.z16, self.fps)
        self.pipeline.start(config)
        return self.pipeline

    def set_recording_state(self, state, trail_path):
        """Start or stop recording based on the state."""
        self.is_recording = state
        self.path = trail_path
        if state:
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self):
        """Starts recording video."""
        base_path = self.path
        self.frame_data_folder = os.path.join(base_path, "Video")
        os.makedirs(self.frame_data_folder, exist_ok=True)

        date_time_str = datetime.now().strftime("%d%m%Y_%H%M%S")
        filename = os.path.join(self.frame_data_folder, f"Video_recorded_{date_time_str}.avi")  # Use .avi format
        
        fourcc = cv2.VideoWriter_fourcc(*'XVID')  # Use XVID for better stability
        self.video_writer = cv2.VideoWriter(filename, fourcc, self.fps, (self.video_width, self.video_height))

        if not self.video_writer.isOpened():
            print("Error: Could not open video writer")
            self.video_writer = None
        else:
            print(f"Recording started: {filename}")

    def stop_recording(self):
        """Stops recording video."""
        if self.video_writer:
            self.video_writer.release()
            self.video_writer = None
            # print("Recording stopped and saved.")
        else:
            print("No active recording to stop.")




    def set_exposure(self, value, auto_exposure=True):
        """Set manual or automatic exposure for the RealSense camera."""
        if self.pipeline is None:
            print("Pipeline is not initialized.")
            return

        try:
            # Get the device
            profile = self.pipeline.get_active_profile()
            device = profile.get_device()
            sensors = device.query_sensors()

            # Find the color sensor
            color_sensor = None
            for sensor in sensors:
                if sensor.get_info(rs.camera_info.name) == 'RGB Camera':
                    color_sensor = sensor
                    break

            if color_sensor is None:
                print("RGB Camera sensor not found.")
                return

            if auto_exposure:
                color_sensor.set_option(rs.option.enable_auto_exposure, 1)
                print("Auto exposure enabled.")
            else:
                color_sensor.set_option(rs.option.enable_auto_exposure, 0)
                color_sensor.set_option(rs.option.exposure, value)
                print(f"Manual exposure set to {value}.")

        except Exception as e:
            print(f"Failed to set exposure: {e}")


    def run_frame(self, w, h):
        """Main loop to capture frames and handle recording."""
        if not self.is_camera_connected():
            print("Please connect a RealSense camera and restart the application.")
            self.running = False
            return

        try:
            pipeline = self.initialize_pipeline(w, h)
            align = rs.align(rs.stream.color)

            while self.running:
                try:
                    frames = pipeline.wait_for_frames()
                    aligned_frames = align.process(frames)

                    color_frame = aligned_frames.get_color_frame()
                    depth_frame = aligned_frames.get_depth_frame()

                    if not color_frame or not depth_frame:
                        continue

                    self.color_frame = np.asanyarray(color_frame.get_data())
                     
                    self.depth_frame = np.asanyarray(depth_frame.get_data())
                     
                    # Resize frame to match video resolution
                    frame_resized = cv2.resize(self.color_frame, (self.video_width, self.video_height))

                    # If recording is enabled, write frame to video
                    if self.is_recording and self.video_writer is not None:
                        if self.video_writer.isOpened():
                            self.video_writer.write(frame_resized)
                        else:
                            print("Error: Video writer is not open.")

                    # Display the color frame
                    # cv2.imshow('RealSense Stream', self.color_frame)

                    # Exit if 'q' or 'Esc' is pressed
                    key = cv2.waitKey(1)
                    if key == 27 or key == ord('q'):
                        # print("Exiting frame capture.")
                        self.running = False
                        break

                except Exception as e:
                    print(f"Error in frame processing: {e}")

            pipeline.stop()
            cv2.destroyAllWindows()

        except Exception as e:
            print(f"Failed to start pipeline: {e}")
            self.running = False

    def stop(self):
        """Stop the frame processing loop and recording if active."""
        self.running = False
        self.stop_recording()

    def get_Frames(self, timeout=5):
        """Safely return copies of the frames if available, waiting for frames if necessary."""
        if not self.running:
            return None, None

        # # Wait until frames are ready or timeout
        # if not self.frames_ready.wait(timeout):
        #     print("Timed out waiting for frames.")
        #     return None, None

        # with self.frames_lock:
        color_copy = copy.deepcopy(self.color_frame)
        depth_copy = copy.deepcopy(self.depth_frame)
        return color_copy, depth_copy

if __name__ == '__main__':
    frame = Frame_Process()
    frame_thread = threading.Thread(target=frame.run_frame, args=(1280, 720))
    frame_thread.start()

    path = r'D:\MOCAP\MOBBO_multiple_board_data_logging\Mobbo_data\ezhil\session4_19032025_100850\trial2'

    time.sleep(2)
    frame.set_recording_state(True, path)  # Start recording

    time.sleep(10)
    frame.set_recording_state(False, path)  # Stop recording

    time.sleep(2)
    frame.set_recording_state(True, path)  # Start another recording

    time.sleep(5)
    frame.set_recording_state(False, path)  # Stop recording again
