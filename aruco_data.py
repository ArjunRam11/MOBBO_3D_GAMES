from cv2 import aruco
import numpy as np
import pyrealsense2 as rs
import msgpack as mp
import msgpack_numpy as mpn
from datetime import datetime
import pickle
import os
import cv2
#it has functions in to run the realsense camera and we can able to identify aruco id in the frame and draw the aruco marker
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
# RS_CAM_MAT_455 = np.array([[638.706, 0, 650.238], [0, 638.706, 350.136], [0, 0, 1]])  # for d455 camera
RS_CAM_MAT_455 = np.array([[645.733, 0, 646.046], [0, 645.733,  361.666], [0, 0, 1]])  # for d455 camera
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
    rvecs, tvecs, _ = [], [], []
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


def run_aruco(w,h,mat,dist):
    pipeline=initialize_pipeline(w,h)
    while True:
            frames = pipeline.wait_for_frames()
            color_frame = frames.get_color_frame()
            image = np.asanyarray(color_frame.get_data())
            corners, ids, rejected_points = aruco.detectMarkers(image, ARUCO_DICT)
            

            if ids is not None:
                ids = ids.flatten()
                corners, ids, rejected_points, _ = DETECTOR.refineDetectedMarkers(
                    image=image,
                    board=BOARD,
                    detectedCorners=corners,
                    detectedIds=ids,
                    rejectedCorners=rejected_points,
                    cameraMatrix=MAT,
                    distCoeffs=DIST
                )
                
                if 11 in ids or 44 in ids:
                    rvecs, tvecs = estimate_pose_single_markers(corners, MARKER_POINTS, mat,dist)
                    my_list = [datetime.now(), ids, tvecs, rvecs]
                    rotation_matrix=cv2.Rodrigues(rvecs[0])[0]  
                    
                    for rvec, tvec in zip(rvecs, tvecs):
                        image = aruco.drawDetectedMarkers(image.copy(), corners=corners, ids=ids)
                        image = cv2.drawFrameAxes(image, mat,dist, rvec, tvec, 0.16)
                    cv2.imshow('RealSense', image)
                    # pickle.dump(my_list, self.aruco_file)
                    yield rotation_matrix
                    # return rotation_matrix

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    pipeline.stop()
    cv2.destroyAllWindows()
 
    



if __name__ == "__main__":
    aruco_generator = run_aruco(1280, 720, MAT, DIST)
    for rotation_matrix in aruco_generator:
        print("Received rvecs:", rotation_matrix)
        