
import numpy as np
import cv2
import numpy as np
from ultralytics import YOLO
# import mediapipe as mdp
import pyrealsense2 as rs
from aruco_data import*
import math 


def create_foot_polygon_3d(   origin, vector2, foot_length, heel_breadth, metacarpal_breadth, metacarpal_height, big_toe_ratio=0.18, pinky_toe_ratio=0.1, is_left=False):
        import numpy as np
        from scipy.spatial import ConvexHull, Delaunay
        import pyqtgraph.opengl as gl
        from itertools import combinations

        # print("the foot polygon function of inside")

         
        origin = np.asarray(origin) #toe   
        vector2 = np.asarray(vector2)   #heel

         
        if origin.ndim == 2 and origin.shape[0] == 1:
            origin = origin.flatten()
        if vector2.ndim == 2 and vector2.shape[0] == 1:
            vector2 = vector2.flatten()

         
        direction_vector = vector2 - origin
        angle = np.arctan2(direction_vector[1], direction_vector[0])

        z_level = origin[2]
        metacarpal_center = np.array([origin[0], origin[1], z_level])
        metacarpal_to_heel_length = foot_length * 0.7
        heel_center = metacarpal_center + np.array(
            [metacarpal_to_heel_length * np.cos(angle), metacarpal_to_heel_length * np.sin(angle), 0]
        )

        # Calculate corners
        heel_left = heel_center + np.array([-heel_breadth / 2 * np.sin(angle), heel_breadth / 2 * np.cos(angle), 0])
        heel_right = heel_center + np.array([heel_breadth / 2 * np.sin(angle), -heel_breadth / 2 * np.cos(angle), 0])
        metacarpal_left = metacarpal_center + np.array(
            [-metacarpal_breadth / 2 * np.sin(angle), metacarpal_breadth / 2 * np.cos(angle), 0]
        )
        metacarpal_right = metacarpal_center + np.array(
            [metacarpal_breadth / 2 * np.sin(angle), -metacarpal_breadth / 2 * np.cos(angle), 0]
        )

        # Big toe and pinky toe points
        big_toe_length = (pinky_toe_ratio if is_left else big_toe_ratio) * foot_length
        pinky_toe_length = (big_toe_ratio if is_left else pinky_toe_ratio) * foot_length

        big_toe_point = metacarpal_right - np.array([big_toe_length * np.cos(angle), big_toe_length * np.sin(angle), 0])
        pinky_toe_point = metacarpal_left - np.array([pinky_toe_length * np.cos(angle), pinky_toe_length * np.sin(angle), 0])

        foot_points = np.array([heel_left, heel_right, metacarpal_right, big_toe_point, pinky_toe_point, metacarpal_left])
        # left = np.array([heel_left, heel_right, metacarpal_right, big_toe_point, pinky_toe_point, metacarpal_left])
        left = np.array([  heel_right, metacarpal_right, big_toe_point, pinky_toe_point ])
        right = np.array([big_toe_point,pinky_toe_point,metacarpal_left,heel_left ])
        # left = np.array([heel_left, heel_right, metacarpal_right, big_toe_point, pinky_toe_point ])
        # right = np.array([big_toe_point,pinky_toe_point,metacarpal_left,heel_left,heel_right ])
        # right = np.array([heel_left, heel_right, metacarpal_right, big_toe_point, pinky_toe_point, metacarpal_left])
         
        
        # foot_polygons_point=np.array([heel_left])
        z_offset = vector2[2] - metacarpal_height
        foot_points[:, 2] = z_offset  # Adjust Z-coordinates
        left[:, 2] = z_offset  # Adjust Z-coordinates
        right[:, 2] = z_offset  # Adjust Z-coordinates


        # foot_points[:, 2] = 0.001  # Adjust Z-coordinates
        # left[:, 2] = 0.001  # Adjust Z-coordinates
        # right[:, 2] = 0.001 # Adjust Z-coordinates


        foot_polygons_point=left if is_left else right

        # print("foot_points: ",  foot_points)

        

        return(foot_polygons_point,foot_points)




def return_BOS_vectors_singlekeypoint_pyqt(tvec_var, rvec_var, tvec_ref, rvec_ref, keypoints_var):
    """
    Transforms keypoints from the variable board frame to the reference board frame
    using the same method as plot_rectangle_3d_points.

    Parameters:
    - tvec_var: Translation vector for the variable board (shape: (3,))
    - rvec_var: Rotation vector for the variable board (shape: (3,))
    - tvec_ref: Translation vector for the reference board (shape: (3,))
    - rvec_ref: Rotation vector for the reference board (shape: (3,))
    - keypoints_var: Keypoints from the variable board (shape: (1, 3) or (23, 3))

    Returns:
    - keypoints_from_ref_board: Transformed keypoints in the reference board frame
      (same shape as input keypoints_var)
    """
    keypoints_var = np.array(keypoints_var)

    # Handle input shape (1, 3) or (23, 3)
    if keypoints_var.ndim == 1:
        keypoints_var = keypoints_var.reshape(1, 3)

    # Compute rotation matrices
    rot_mat_ref, _ = cv2.Rodrigues(rvec_ref)
    rot_mat_var, _ = cv2.Rodrigues(rvec_var)

    tvec_ref = tvec_ref.reshape(3, 1)
    tvec_var = tvec_var.reshape(3, 1)

    # Compute relative rotation and translation
    relative_rot_mat = np.matmul(np.transpose(rot_mat_ref), rot_mat_var)
    relative_translation = np.matmul(np.transpose(rot_mat_ref), (tvec_var - tvec_ref))

    # Transform keypoints
    keypoints_from_ref_board = []
    for keypoint in keypoints_var:
        keypoint = keypoint.reshape(3, 1)

        # Step 1: Transform keypoint to the variable board's local frame
        keypoint_local_board = np.matmul(np.transpose(rot_mat_var), (keypoint - tvec_var))

        # Step 2: Transform keypoint to the reference board's frame
        keypoint_relative = np.matmul(np.transpose(relative_rot_mat), keypoint_local_board)
        transformed_keypoint = keypoint_relative + relative_translation

        keypoints_from_ref_board.append(transformed_keypoint.flatten())

    return np.array(keypoints_from_ref_board)
