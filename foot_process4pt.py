import numpy as np
import threading
import cv2
from aruco_realsense import *
from ultralytics import YOLO
import pyrealsense2 as rs
from Frame_Process import *
import time

ARUCO_DICT        = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_ARUCO_ORIGINAL)
ARUCO_PARAMETERS  = cv2.aruco.DetectorParameters()
DETECTOR          = cv2.aruco.ArucoDetector(ARUCO_DICT, ARUCO_PARAMETERS)
MARKER_LENGTH     = 0.304
MARKER_SEPARATION = 0.043

foot_thread_flag = True

# ── 4-point model keypoint order (must match model training) ──────────────────
# Index: 0 = pinky, 1 = mid, 2 = big_toe, 3 = heel
FOOT_PARTS     = ["pinky", "mid", "big_toe", "heel"]
CROP_HALF_SIZE = 0.325   # metres – half-size of the projected crop region

# Colours per keypoint part (BGR)
PART_COLORS = {
    "pinky":   (255, 0,   0),    # blue
    "mid":     (0,   255, 255),  # yellow
    "big_toe": (0,   255, 0),    # green
    "heel":    (0,   0,   255),  # red
}
SIDE_COLORS = {
    "right": (0,   255, 0),   # green outline
    "left":  (255, 100, 0),   # orange outline
}


class foot_detector():

    def __init__(self):
        self.target_ids = [11, 68, 55,88,33,44]

        # ── Update this path to your 4-point model ───────────────────────
        self.foot_predict = YOLO(fr'E:\OpenCV_mobbo_works\BaseOfSupport\notebooks\runs\pose\train3\weights\best.pt')

        # Warmup: run a dummy inference so CUDA kernels are compiled before
        # the first real frame arrives — prevents the 200ms+ cold-start spike
        _dummy = np.zeros((240, 320, 3), dtype=np.uint8)
        self.foot_predict.predict([_dummy, _dummy], conf=0.5, verbose=False, device=0)
        print("✅ YOLO GPU warmup complete")
        # ─────────────────────────────────────────────────────────────────

        self.keypoints = None
        self.depth     = None
        self.image     = None   # ← always holds the LATEST annotated frame

    # ── Public API ────────────────────────────────────────────────────────────

    def start_detection(self, frame2):
        global foot_thread_flag
        foot_thread_flag = True
        self.thread = threading.Thread(
            target=self.detect_foot,
            args=(1280, 720, MAT, DIST, self.target_ids, frame2)
        )
        self.thread.start()

    def foot_prediction_stopthread(self):
        global foot_thread_flag
        foot_thread_flag = False

    def get_keypoints(self):
        """Returns (keypoints_dict, depth_frame, annotated_color_image)."""
        return self.keypoints, self.depth, self.image

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _normalize_to_pixel(xy_norm, xmin, xmax, ymin, ymax):
        x = int(xmin + xy_norm[0] * (xmax - xmin))
        y = int(ymin + xy_norm[1] * (ymax - ymin))
        return x, y

    @staticmethod
    def _draw_keypoints_on_frame(color_image, keypoints_dict):
        """
        Draw every detected keypoint on the full-resolution image.
        - Large filled circle coloured by body part
        - Label text (side + part name)
        - Lines connecting heel → big_toe and heel → pinky per foot
        """
        if not keypoints_dict:
            return

        # ── Circles + labels ──────────────────────────────────────────────
        for key, pt in keypoints_dict.items():
            # key format: "right_big_toe", "left_heel", etc.
            side = "right" if key.startswith("right") else "left"
            part = key[len(side) + 1:]          # strip "right_" / "left_"
            color = PART_COLORS.get(part, (255, 255, 255))

            cv2.circle(color_image, pt, radius=6, color=color, thickness=-1)
            cv2.circle(color_image, pt, radius=8,
                       color=SIDE_COLORS[side], thickness=2)   # outline

        # ── Skeleton lines per foot ───────────────────────────────────────
        for side in ("right", "left"):
            heel    = keypoints_dict.get(f"{side}_heel")
            big_toe = keypoints_dict.get(f"{side}_big_toe")
            pinky   = keypoints_dict.get(f"{side}_pinky")
            mid     = keypoints_dict.get(f"{side}_mid")

            line_color = SIDE_COLORS[side]

            # Connect all adjacent points: heel-big_toe, heel-pinky,
            # pinky-mid, mid-big_toe (rough foot outline)
            pairs = [
                (heel,    big_toe),
                (heel,    pinky),
                (pinky,   mid),
                (mid,     big_toe),
            ]
            for p1, p2 in pairs:
                if p1 is not None and p2 is not None:
                    cv2.line(color_image, p1, p2, line_color, 2, cv2.LINE_AA)

    # ── Detection thread ──────────────────────────────────────────────────────

    def detect_foot(self, w, h, mat, dist, target_ids, frame2):
        global foot_thread_flag

        a = CROP_HALF_SIZE
        corners_board = np.array([
            [ a,  a, 0.0],
            [-a,  a, 0.0],
            [-a, -a, 0.0],
            [ a, -a, 0.0]
        ], dtype=np.float32).reshape(-1, 1, 3)

        frame_count  = 0
        stored_rvecs = {}

        # ── DIAG state ────────────────────────────────────────────────────────
        _diag_loop_count  = 0
        _diag_total_loop  = 0.0
        _diag_total_yolo  = 0.0
        _diag_total_aruco = 0.0
        _diag_yolo_calls  = 0
        _diag_t_loop_start = time.time()
        # ── END DIAG state ────────────────────────────────────────────────────

        # ── FPS display state ─────────────────────────────────────────────────
        _fps_prev_time = time.time()
        _fps_display   = 0.0
        # ─────────────────────────────────────────────────────────────────────

        stored_tvecs    = {}
        detected_ids    = set(target_ids)
        _last_keypoints = None   # cached keypoints for YOLO skip frames

        # Detection status for HUD
        status_msg   = "Initialising..."
        det_count    = {"right": 0, "left": 0}

        while True:
            if not foot_thread_flag:
                break

            _diag_t0 = time.time()  # DIAG: loop start
            color_frame, depth_frame = frame2.get_Frames()

            if (color_frame is None or depth_frame is None
                    or color_frame.size == 0 or depth_frame.size == 0):
                print("Warning: Empty frame received, retrying...")
                time.sleep(0.1)
                continue

            color_image  = color_frame.copy()
            self.depth   = depth_frame
            # NOTE: self.image is updated at the END of the loop so it
            # always carries the fully-annotated frame.

            # ── ArUco detection & pose estimation ─────────────────────────
            _diag_ta0 = time.time()  # DIAG
            half_frame = cv2.resize(color_image, (640, 360))
            corners_half, ids, _ = cv2.aruco.detectMarkers(half_frame, ARUCO_DICT)
            # Scale corners back to full-res so projectPoints stays accurate
            corners = [c * 2.0 for c in corners_half] if corners_half else corners_half
            _diag_total_aruco += time.time() - _diag_ta0  # DIAG
            frame_count += 1

            # Draw all detected ArUco markers for reference
            if ids is not None:
                cv2.aruco.drawDetectedMarkers(color_image, corners, ids)

            if frame_count <= 10:
                status_msg = f"Warming up... ({frame_count}/10)"
                if ids is not None:
                    detected_ids.update(ids.flatten())
                    rvecs, tvecs = estimate_pose_single_markers(
                        corners, MARKER_POINTS, mat, dist
                    )
                    if rvecs is not None and tvecs is not None:
                        for i, mid in enumerate(ids.flatten()):
                            if mid in target_ids:
                                stored_rvecs[mid] = rvecs[i]
                                stored_tvecs[mid] = tvecs[i]

            elif frame_count > 10 and detected_ids:
                status_msg = "Running detection"

                # ── Throttle solvePnP: update poses every 3rd frame only ───
                if ids is not None and (frame_count % 3 == 0):
                    valid_indices = [
                        i for i, mid in enumerate(ids.flatten())
                        if mid in detected_ids
                    ]
                    if valid_indices:
                        valid_corners = [corners[i] for i in valid_indices]
                        rvecs, tvecs  = estimate_pose_single_markers(
                            valid_corners, MARKER_POINTS, mat, dist
                        )
                        for i, mid in enumerate(ids.flatten()[valid_indices]):
                            stored_rvecs[mid] = rvecs[i]
                            stored_tvecs[mid] = tvecs[i]

                # ── Build crop list for batched YOLO ───────────────────────
                crops, crop_meta = [], []
                det_count = {"right": 0, "left": 0}

                for marker_id in stored_rvecs:
                    if marker_id not in target_ids:
                        continue

                    rvec = stored_rvecs[marker_id]
                    tvec = stored_tvecs[marker_id]

                    projected, _ = cv2.projectPoints(
                        corners_board, rvec, tvec, mat, dist
                    )
                    projected = projected.astype(int)

                    x_min = max(0, min(p[0][0] for p in projected))
                    x_max = min(color_image.shape[1], max(p[0][0] for p in projected))
                    y_min = max(0, min(p[0][1] for p in projected))
                    y_max = min(color_image.shape[0], max(p[0][1] for p in projected))

                    if x_max <= x_min or y_max <= y_min:
                        continue

                    cropped = color_image[y_min:y_max, x_min:x_max]
                    resized = cv2.resize(cropped, (320, 240))   # smaller = faster
                    crops.append(resized)
                    crop_meta.append((marker_id, x_min, x_max, y_min, y_max))

                # ── Single batched YOLO call every other frame ─────────────
                if crops and (frame_count % 2 == 0):
                    combined_keypoints = {}
                    _diag_ty0 = time.time()
                    all_results = self.foot_predict.predict(
                        crops, conf=0.5, verbose=False, device=0
                    )
                    _diag_total_yolo += time.time() - _diag_ty0
                    _diag_yolo_calls += 1

                    for results, (marker_id, x_min, x_max, y_min, y_max) in zip(all_results, crop_meta):
                        if results.keypoints is None:
                            status_msg = f"ID:{marker_id} – no keypoints"
                            continue

                        x_norm = results.keypoints.xyn.cpu().numpy()
                        _cls   = results.boxes.cls.cpu().numpy()

                        if x_norm.shape == (2, 4, 2):
                            sides = (["right", "left"] if _cls[0] == 0
                                     else ["left", "right"])
                            for i, side in enumerate(sides):
                                det_count[side] += 1
                                for j, part in enumerate(FOOT_PARTS):
                                    px, py = self._normalize_to_pixel(
                                        x_norm[i][j], x_min, x_max, y_min, y_max
                                    )
                                    combined_keypoints[f"{side}_{part}"] = (px, py)
                            status_msg = "BOTH feet detected ✓"

                        elif x_norm.shape == (1, 4, 2):
                            side = "right" if _cls[0] == 0 else "left"
                            det_count[side] += 1
                            for j, part in enumerate(FOOT_PARTS):
                                px, py = self._normalize_to_pixel(
                                    x_norm[0][j], x_min, x_max, y_min, y_max
                                )
                                combined_keypoints[f"{side}_{part}"] = (px, py)
                            status_msg = f"{side.upper()} foot detected ✓"

                        else:
                            status_msg = (f"ID:{marker_id} – unexpected shape "
                                          f"{x_norm.shape}")

                    _last_keypoints  = combined_keypoints if combined_keypoints else None
                    self.keypoints   = _last_keypoints
                else:
                    # Skipped YOLO frame — reuse last result
                    self.keypoints = _last_keypoints

                # Draw all keypoints + skeleton on the full-res frame
                self._draw_keypoints_on_frame(color_image, self.keypoints)

            # ── Per-frame FPS ─────────────────────────────────────────────
            _now = time.time()
            _dt  = _now - _fps_prev_time
            _fps_prev_time = _now
            _fps_display = 1.0 / _dt if _dt > 0 else _fps_display

            # ── HUD overlay ───────────────────────────────────────────────
            # Status bar at top
            cv2.rectangle(color_image, (0, 0), (color_image.shape[1], 30),
                          (30, 30, 30), -1)
            cv2.putText(color_image,
                        f"Frame {frame_count} | {status_msg} | FPS: {_fps_display:.1f}",
                        (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                        (255, 255, 255), 1, cv2.LINE_AA)

            # Keypoint count bottom-left
            n_kp = len(self.keypoints) if self.keypoints else 0
            cv2.putText(color_image,
                        f"Keypoints: {n_kp}/8  R:{det_count['right']}  L:{det_count['left']}",
                        (8, color_image.shape[0] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                        (0, 255, 255), 1, cv2.LINE_AA)

            # ── Update shared image AFTER all drawing is done ─────────────
            # This is the fix: self.image now always carries the annotated frame
            self.image = color_image

            # ── DIAG: per-loop timing + periodic report ───────────────────
            _diag_loop_count += 1
            _diag_total_loop += time.time() - _diag_t0
            if _diag_loop_count % 50 == 0:
                elapsed  = time.time() - _diag_t_loop_start
                avg_loop = (_diag_total_loop  / _diag_loop_count) * 1000
                avg_aruco= (_diag_total_aruco / _diag_loop_count) * 1000
                avg_yolo = (_diag_total_yolo  / _diag_yolo_calls) * 1000 if _diag_yolo_calls else 0
                fps      = _diag_loop_count / elapsed if elapsed > 0 else 0
                print(
                    f"[DIAG foot] fps={fps:.1f}  loop={avg_loop:.1f}ms  "
                    f"aruco={avg_aruco:.1f}ms  "
                    f"yolo={avg_yolo:.1f}ms/call × {_diag_yolo_calls // max(_diag_loop_count,1)} calls/frame  "
                    f"(markers tracked={len(stored_rvecs)})"
                )
                # reset accumulators
                _diag_loop_count = _diag_yolo_calls = 0
                _diag_total_loop = _diag_total_yolo = _diag_total_aruco = 0.0
                _diag_t_loop_start = time.time()
            # ── END DIAG ──────────────────────────────────────────────────

            # ── Live debug window (full frame) ────────────────────────────
            cv2.imshow("Foot Detection – Full Frame", color_image)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        foot_thread_flag = False
        cv2.destroyAllWindows()


# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    frame = Frame_Process()
    ft = threading.Thread(target=frame.run_frame, args=(1280, 720))
    ft.start()
    time.sleep(1)
    predict = foot_detector()
    predict.start_detection(frame)

    # Keep main thread alive so windows stay open
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        predict.foot_prediction_stopthread()
        print("Stopped.")
