
import numpy as np
import cv2
import numpy as np
from ultralytics import YOLO
# import mediapipe as mdp
import pyrealsense2 as rs
from aruco_data import*
import math 


def create_foot_polygon_3d(origin, vector2, foot_length, heel_breadth, metacarpal_breadth,
                           metacarpal_height, big_toe_ratio=0.18, pinky_toe_ratio=0.1,
                           is_left=False):
        # origin: toe point, vector2: heel point (both in reference-board frame)
        toe = np.asarray(origin, dtype=float).reshape(-1)[:3]
        heel = np.asarray(vector2, dtype=float).reshape(-1)[:3]

        if toe.shape[0] < 3 or heel.shape[0] < 3:
            return None, None

        foot_vec_xy = toe[:2] - heel[:2]  # heel -> toe direction
        measured_length = np.linalg.norm(foot_vec_xy)
        if measured_length < 1e-9:
            forward_xy = np.array([1.0, 0.0], dtype=float)
            measured_length = float(foot_length)
        else:
            forward_xy = foot_vec_xy / measured_length

        left_xy = np.array([-forward_xy[1], forward_xy[0]], dtype=float)

        # Keep forefoot slightly behind toe tip while staying anchored to measured keypoints.
        toe_inset = float(np.clip(metacarpal_height, 0.0, 0.25 * max(float(foot_length), 1e-6)))
        metacarpal_center_xy = toe[:2] - forward_xy * toe_inset
        heel_center_xy = heel[:2]

        heel_left_xy = heel_center_xy + left_xy * (heel_breadth * 0.5)
        heel_right_xy = heel_center_xy - left_xy * (heel_breadth * 0.5)
        metacarpal_left_xy = metacarpal_center_xy + left_xy * (metacarpal_breadth * 0.5)
        metacarpal_right_xy = metacarpal_center_xy - left_xy * (metacarpal_breadth * 0.5)

        model_length = max(float(foot_length), measured_length)
        big_toe_length = (pinky_toe_ratio if is_left else big_toe_ratio) * model_length
        pinky_toe_length = (big_toe_ratio if is_left else pinky_toe_ratio) * model_length

        big_toe_xy = metacarpal_right_xy + forward_xy * big_toe_length
        pinky_toe_xy = metacarpal_left_xy + forward_xy * pinky_toe_length

        z_level = float(np.nanmean([toe[2], heel[2]]) - metacarpal_height)
        foot_points = np.array([
            [heel_left_xy[0], heel_left_xy[1], z_level],
            [heel_right_xy[0], heel_right_xy[1], z_level],
            [metacarpal_right_xy[0], metacarpal_right_xy[1], z_level],
            [big_toe_xy[0], big_toe_xy[1], z_level],
            [pinky_toe_xy[0], pinky_toe_xy[1], z_level],
            [metacarpal_left_xy[0], metacarpal_left_xy[1], z_level],
        ], dtype=float)

        # Use full foot boundary for BOS hull construction.
        foot_polygons_point = foot_points.copy()
        return foot_polygons_point, foot_points




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
