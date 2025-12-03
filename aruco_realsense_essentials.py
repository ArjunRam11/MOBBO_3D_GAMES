from cv2 import aruco
import numpy as np
import pyrealsense2 as rs
import cv2



# ArUco marker configuration
ARUCO_DICT = aruco.getPredefinedDictionary(aruco.DICT_ARUCO_ORIGINAL)
ARUCO_PARAMETERS = aruco.DetectorParameters()
DETECTOR = aruco.ArucoDetector(ARUCO_DICT, ARUCO_PARAMETERS)
MARKER_LENGTH = 0.304
MARKER_SEPARATION = 0.043
BOARD = aruco.GridBoard(
    size=[1, 1],
    markerLength=MARKER_LENGTH,
    markerSeparation=MARKER_SEPARATION,
    dictionary=ARUCO_DICT
)

# Camera calibration
RS_CAM_MAT_455 = np.array([[638.706, 0, 650.238], [0, 638.706, 350.136], [0, 0, 1]])  # for d455 camera
MAT = RS_CAM_MAT_455.reshape(3, 3)
DIST = np.zeros((1, 5))

# Marker points for pose estimation
MARKER_POINTS = np.array([
    [-MARKER_LENGTH / 2, MARKER_LENGTH / 2, 0],
    [MARKER_LENGTH / 2, MARKER_LENGTH / 2, 0],
    [MARKER_LENGTH / 2, -MARKER_LENGTH / 2, 0],
    [-MARKER_LENGTH / 2, -MARKER_LENGTH / 2, 0]
], dtype=np.float32)


def estimate_pose_single_markers(corners, marker_points, mtx, distortion):
    rvecs, tvecs = [], []
    for c in corners:
        _, R, t = cv2.solvePnP(marker_points, c, mtx, distortion, False, flags=cv2.SOLVEPNP_ITERATIVE)
        rvecs.append(R.reshape((1, 3)))
        tvecs.append(t.reshape((1, 3)))
    return rvecs, tvecs



def initialize_pipeline(width, height):
    pipeline = rs.pipeline()
    config = rs.config()
    config.enable_stream(rs.stream.color, width, height, rs.format.bgr8, 30)
    config.enable_stream(rs.stream.depth, width, height, rs.format.z16, 30)
    pipeline.start(config)
    return pipeline