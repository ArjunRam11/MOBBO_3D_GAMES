import math
import time
import cv2
from cv2 import aruco
import numpy as np 
from _mobbo_setup_utilities import *
import os
 
aruco_dict = cv2.aruco.getPredefinedDictionary(aruco.DICT_ARUCO_ORIGINAL)
h=720
w=1280
ARUCO_PARAMETERS = aruco.DetectorParameters()
ARUCO_DICT = aruco.getPredefinedDictionary(aruco.DICT_ARUCO_ORIGINAL)
detector = aruco.ArucoDetector(ARUCO_DICT, ARUCO_PARAMETERS)
markerLength = 0.304
markerSeperation = 0.043
board = aruco.GridBoard(
        size= [1,1],
        markerLength=markerLength,
        markerSeparation=markerSeperation,
        dictionary=ARUCO_DICT)

rotation_vectors, translation_vectors = None, None
axis = np.float32([[-.5, -.5, 0], [-.5, .5, 0], [.5, .5, 0], [.5, -.5, 0],
                   [-.5, -.5, 1], [-.5, .5, 1], [.5, .5, 1], [.5, -.5, 1]])
marker_size = markerLength
marker_points = np.array([[-marker_size / 2, marker_size / 2, 0],
                            [marker_size / 2, marker_size / 2, 0],
                            [marker_size / 2, -marker_size / 2, 0],
                            [-marker_size / 2, -marker_size / 2, 0]], dtype=np.float32)

rs_cam_mat_455=np.array([[638.706,0,650.238],[0,638.706,350.136],[0,0,1]]) #for d455 camera
mat = rs_cam_mat_455.reshape(3,3)
dist = np.zeros((1,5))


def my_estimatePoseSingleMarkers(corners, marker_points, mtx, distortion):

    trash = []
    rvecs = []
    tvecs = []
    for c in corners:
        nada, R, t = cv2.solvePnP(marker_points, c, mtx, distortion, False, flags= cv2.SOLVEPNP_ITERATIVE)
        R = R.reshape((1, 3))
        t = t.reshape((1, 3))
        rvecs.append(R)
        tvecs.append(t)
        trash.append(nada)
    return rvecs, tvecs, trash


def camera_functions(pipeline,mat,dist):

    camera_start_time=time.time()
    counter = 0
    frames=[]
    point_corner = [(0.3, 0.225, 0), (-0.3, 0.225, 0), (-0.3, -0.225, 0), (0.3, -0.225, 0)]
    pixelregion_corner = [(0.1, -0.125, 0), (-0.1,-0.125, 0), (-0.1, -0.225, 0), (0.1, -0.225, 0)]

    board_setupdata={'board_corners':[],'ids':[], 'led_regions':[],'board_3dpos':[],'centre':[],'rotation_matrices':[]}
    while True:
            
            color_frame,frame_depth=pipeline.get_Frames()
            image=cv2.cvtColor(color_frame,   cv2.COLOR_BGR2RGB)
            image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

            corners, ids, rejectedPoints = aruco.detectMarkers(image, aruco_dict)
            corners, ids, rejectedpoints,_ = detector.refineDetectedMarkers(image=image,board=board ,detectedCorners=corners, detectedIds=ids, rejectedCorners=rejectedPoints, cameraMatrix=mat, distCoeffs=dist)
            if ids is not None:

                for idx,id in enumerate(ids):

                    if(id==11 or id==44 or id==68 or id==88):

                        rotation_vectors, translation_vectors, _objPoints = my_estimatePoseSingleMarkers(corners, marker_points, mat, dist)  
                        rotation_vectors = np.array(rotation_vectors)
                        translation_vectors = np.array(translation_vectors)
                        rmat =np.array(cv2.Rodrigues(rotation_vectors[idx])[0])

                        rot_vec = rmat.T @ (translation_vectors[idx][0]).reshape(3,1)
                        centre=np.mean(corners[idx],axis=1)

                        board_setupdata['board_3dpos'].append(translation_vectors)

                        if(len(board_setupdata['centre'])<len(ids)):

                            board_setupdata['centre'].append(centre)
                            board_setupdata['rotation_matrices'].append(rmat)

                        for rvec, tvec in zip(rotation_vectors, translation_vectors):
                                
                                image = aruco.drawDetectedMarkers(image, corners=corners, ids=ids)
                                image = cv2.drawFrameAxes(image, mat, dist, rvec, tvec, 0.25)
                        projected_point, _ = cv2.projectPoints(np.array(point_corner), rmat, translation_vectors[idx], mat,dist)  
                        led_reg_point, _ = cv2.projectPoints(np.array(pixelregion_corner), rmat, translation_vectors[idx], mat,dist)  
                        image_coordinates = np.squeeze(np.round(projected_point)).astype(int) 
                        led_reg_coordinates=np.squeeze(np.round(led_reg_point)).astype(int) 

                        if(len(board_setupdata['board_corners'])<(len(ids))):
                            board_setupdata['board_corners'].append(image_coordinates)
                            board_setupdata['led_regions'].append(led_reg_coordinates)
                        cv2.polylines(image,np.int32([image_coordinates]),  1, (0,0,0),thickness=1)
                        for i in image_coordinates:
                            cv2.circle(image, i, 4, (255,255,255),-1) 
                            cv2.aruco.drawDetectedMarkers(image, corners, ids)
                            board_setupdata['ids'].append(ids)

            cv2.imshow('ArUco Marker Detection', image) 
            counter+=1
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            if counter==20:
                break
    cv2.destroyAllWindows()
    camera_end_time=time.time()
    full_time =  camera_end_time- camera_start_time  # Calculate the difference
    # print(f"The camera execution time of the full program: {full_time:.5f} seconds")
    return board_setupdata

 

def process_image (image, mat, dist):
    """
    Process a single input image to detect ArUco markers and extract data.

    Args:
        image (numpy.ndarray): The input image in BGR format.
        mat (numpy.ndarray): Camera intrinsic matrix.
        dist (numpy.ndarray): Distortion coefficients.

    Returns:
        dict: A dictionary containing board setup data.
    """

    image=cv2.imread(image)
    point_corner = [(0.3, 0.225, 0), (-0.3, 0.225, 0), (-0.3, -0.225, 0), (0.3, -0.225, 0)]
    pixelregion_corner = [(0.1, -0.125, 0), (-0.1, -0.125, 0), (-0.1, -0.225, 0), (0.1, -0.225, 0)]

    board_setupdata = {
        'board_corners': [],
        'ids': [],
        'led_regions': [],
        'board_3dpos': [],
        'centre': [],
        'rotation_matrices': []
    }

    # Convert the image to RGB and back to BGR (simulates processing pipeline)
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

    # Detect markers in the image
    corners, ids, rejectedPoints = aruco.detectMarkers(image, aruco_dict)
    corners, ids, rejectedpoints, _ = detector.refineDetectedMarkers(
        image=image,
        board=board,
        detectedCorners=corners,
        detectedIds=ids,
        rejectedCorners=rejectedPoints,
        cameraMatrix=mat,
        distCoeffs=dist
    )

    if ids is not None:
        for idx, id in enumerate(ids):
            if id == 11 or id == 44 or id == 68 or id == 88:
                # Estimate pose
                rotation_vectors, translation_vectors, _objPoints = my_estimatePoseSingleMarkers(
                    corners, marker_points, mat, dist
                )
                rotation_vectors = np.array(rotation_vectors)
                translation_vectors = np.array(translation_vectors)
                rmat = np.array(cv2.Rodrigues(rotation_vectors[idx])[0])

                # Transformations
                rot_vec = rmat.T @ (translation_vectors[idx][0]).reshape(3, 1)
                centre = np.mean(corners[idx], axis=1)

                # Store data in the dictionary
                board_setupdata['board_3dpos'].append(translation_vectors)

                if len(board_setupdata['centre']) < len(ids):
                    board_setupdata['centre'].append(centre)
                    board_setupdata['rotation_matrices'].append(rmat)

                for rvec, tvec in zip(rotation_vectors, translation_vectors):
                    image = aruco.drawDetectedMarkers(image, corners=corners, ids=ids)
                    image = cv2.drawFrameAxes(image, mat, dist, rvec, tvec, 0.25)

                # Project points
                projected_point, _ = cv2.projectPoints(
                    np.array(point_corner), rmat, translation_vectors[idx], mat, dist
                )
                led_reg_point, _ = cv2.projectPoints(
                    np.array(pixelregion_corner), rmat, translation_vectors[idx], mat, dist
                )

                # Convert to integer coordinates
                image_coordinates = np.squeeze(np.round(projected_point)).astype(int)
                led_reg_coordinates = np.squeeze(np.round(led_reg_point)).astype(int)

                if len(board_setupdata['board_corners']) < len(ids):
                    board_setupdata['board_corners'].append(image_coordinates)
                    board_setupdata['led_regions'].append(led_reg_coordinates)

                # Draw markers on the image
                cv2.polylines(image, np.int32([image_coordinates]), 1, (0, 0, 0), thickness=1)
                for i in image_coordinates:
                    cv2.circle(image, i, 4, (255, 255, 255), -1)
                    cv2.aruco.drawDetectedMarkers(image, corners, ids)

                board_setupdata['ids'].append(ids)

    
    # cv2.imshow('ArUco Marker Detection', image)
    # cv2.waitKey(0)
    # cv2.destroyAllWindows()
    

    return board_setupdata