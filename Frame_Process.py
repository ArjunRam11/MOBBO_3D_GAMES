"""
Frame_Process.py

RealSense camera pipeline.
Video is saved to a dedicated Video/ folder inside the session root,
NOT inside the CoP trial folder.

If you don't need video, call set_recording_state with enable_video=False
(default) and no video files will be created at all.
"""

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
        self.frames_lock  = threading.Lock()
        self.color_frame  = None
        self.depth_frame  = None
        self.running      = True
        self.is_recording = False
        self.video_writer = None
        self._video_folder = None
        self.fps          = 30
        self.video_width  = 1280
        self.video_height = 720
        self.pipeline     = None
        self._enable_video = False   # Video disabled by default

    # ─────────────────────────────────────────────────────────────────────────

    def is_camera_connected(self) -> bool:
        context = rs.context()
        return len(context.devices) > 0

    def initialize_pipeline(self, width, height):
        self.pipeline = rs.pipeline()
        config = rs.config()
        config.enable_stream(rs.stream.color, width, height, rs.format.bgr8, self.fps)
        config.enable_stream(rs.stream.depth, width, height, rs.format.z16, self.fps)
        self.pipeline.start(config)
        return self.pipeline

    # ─────────────────────────────────────────────────────────────────────────

    def set_recording_state(self, state: bool, session_path: str = None,
                            enable_video: bool = False):
        """
        Start or stop recording.

        Args:
            state        : True = start recording, False = stop
            session_path : Root session folder (Video/ subfolder created here).
                           If None or enable_video=False, no video is saved.
            enable_video : Set True to save video. Default False (not needed).
        """
        self.is_recording  = state
        self._enable_video = enable_video

        if state and enable_video and session_path:
            self._start_video(session_path)
        else:
            if not state:
                self._stop_video()

    def _start_video(self, session_path: str):
        """Save video into session_path/Video/ folder."""
        self._video_folder = os.path.join(session_path, "Video")
        os.makedirs(self._video_folder, exist_ok=True)

        ts       = datetime.now().strftime("%d%m%Y_%H%M%S")
        filename = os.path.join(self._video_folder, f"Video_recorded_{ts}.avi")

        fourcc            = cv2.VideoWriter_fourcc(*'XVID')
        self.video_writer = cv2.VideoWriter(
            filename, fourcc, self.fps, (self.video_width, self.video_height)
        )

        if not self.video_writer.isOpened():
            print(f"❌ Could not open video writer: {filename}")
            self.video_writer = None
        else:
            print(f"🎥 Video recording started: {filename}")

    def _stop_video(self):
        if self.video_writer:
            self.video_writer.release()
            self.video_writer = None
            print("🎥 Video recording stopped")

    # ─────────────────────────────────────────────────────────────────────────

    def run_frame(self, w, h):
        if not self.is_camera_connected():
            print("No RealSense camera detected.")
            self.running = False
            return

        try:
            pipeline = self.initialize_pipeline(w, h)
            align    = rs.align(rs.stream.color)

            while self.running:
                try:
                    frames         = pipeline.wait_for_frames()
                    aligned_frames = align.process(frames)
                    color_frame    = aligned_frames.get_color_frame()
                    depth_frame    = aligned_frames.get_depth_frame()

                    if not color_frame or not depth_frame:
                        continue

                    self.color_frame = np.asanyarray(color_frame.get_data())
                    self.depth_frame = np.asanyarray(depth_frame.get_data())

                    if self.is_recording and self._enable_video and self.video_writer:
                        frame_resized = cv2.resize(
                            self.color_frame, (self.video_width, self.video_height)
                        )
                        if self.video_writer.isOpened():
                            self.video_writer.write(frame_resized)

                    key = cv2.waitKey(1)
                    if key in (27, ord('q')):
                        self.running = False
                        break

                except Exception as e:
                    print(f"Frame error: {e}")

            pipeline.stop()
            cv2.destroyAllWindows()

        except Exception as e:
            print(f"Pipeline error: {e}")
            self.running = False

    def stop(self):
        self.running = False
        self._stop_video()

    def get_Frames(self, timeout=5):
        if not self.running:
            return None, None
        color_copy = copy.deepcopy(self.color_frame)
        depth_copy = copy.deepcopy(self.depth_frame)
        return color_copy, depth_copy

    def set_exposure(self, value, auto_exposure=True):
        if self.pipeline is None:
            return
        try:
            profile     = self.pipeline.get_active_profile()
            device      = profile.get_device()
            sensors     = device.query_sensors()
            color_sensor = next(
                (s for s in sensors
                 if s.get_info(rs.camera_info.name) == 'RGB Camera'), None
            )
            if color_sensor is None:
                return
            if auto_exposure:
                color_sensor.set_option(rs.option.enable_auto_exposure, 1)
            else:
                color_sensor.set_option(rs.option.enable_auto_exposure, 0)
                color_sensor.set_option(rs.option.exposure, value)
        except Exception as e:
            print(f"Exposure error: {e}")