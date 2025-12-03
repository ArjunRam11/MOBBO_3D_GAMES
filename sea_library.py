import cv2
import numpy as np
from ultralytics import YOLO
import mediapipe as mdp
import pyrealsense2 as rs
from aruco_data import*
import math 

 
mp_pose = mdp.solutions.pose
# pose = mp_pose.Pose(min_detection_confidence=0.7, min_tracking_confidence=0.5)
pose = mp_pose.Pose(min_detection_confidence=0.8, min_tracking_confidence=0.7)
mp_draw = mdp.solutions.drawing_utils


camera_matrix=RS_CAM_MAT_455  



def get_keypoints_3d_sealibrary(landmarks, depth_frame, camera_matrix):
    keypoints_3d = {}

    h, w = depth_frame.shape

    # Define the keypoints you want to extract
    
    # MediaPipe keypoint mapping for a human skeleton
    keypoints = {
         'head': mp_pose.PoseLandmark.NOSE,  # Using the nose as the "head" for simplicity  0
        'neck': mp_pose.PoseLandmark.RIGHT_SHOULDER,  # Using the right shoulder to approximate the neck  1
        'right_shoulder': mp_pose.PoseLandmark.RIGHT_SHOULDER,  #2
        'left_shoulder': mp_pose.PoseLandmark.LEFT_SHOULDER,    #3
        'right_elbow': mp_pose.PoseLandmark.RIGHT_ELBOW,        #4
        'left_elbow': mp_pose.PoseLandmark.LEFT_ELBOW,          #5
        'right_hand': mp_pose.PoseLandmark.RIGHT_WRIST,         #6
        'left_hand': mp_pose.PoseLandmark.LEFT_WRIST,           #7
        'right_hip': mp_pose.PoseLandmark.RIGHT_HIP,            #8
        'left_hip': mp_pose.PoseLandmark.LEFT_HIP,              #9
        'right_knee': mp_pose.PoseLandmark.RIGHT_KNEE,          #10
        'left_knee': mp_pose.PoseLandmark.LEFT_KNEE,            #11
        'right_foot': mp_pose.PoseLandmark.RIGHT_ANKLE,         #12
        'left_foot': mp_pose.PoseLandmark.LEFT_ANKLE,           #13
        'left_heel': mp_pose.PoseLandmark.LEFT_HEEL,            #14
        'right_heel': mp_pose.PoseLandmark.RIGHT_HEEL,          #15
        'left_foot_index': mp_pose.PoseLandmark.LEFT_FOOT_INDEX,#16
        'right_foot_index': mp_pose.PoseLandmark.RIGHT_FOOT_INDEX#17
    }


    for name, landmark in keypoints.items():
        u, v = int(landmarks[landmark.value].x * w), int(landmarks[landmark.value].y * h)

        if 0 <= u < w and 0 <= v < h:  # Boundary check
            depth = depth_frame[v, u] * 0.001  # Convert depth to meters
            keypoints_3d[name] = pixel_to_world_sealibrary(u, v, depth, camera_matrix)
        else:
            # keypoints_3d[name] = None  # Handle out-of-bounds case
            keypoints_3d[name] = np.array([0,0,0]) # Handle out-of-bounds case

    return keypoints_3d

# it is use in key 
keypoints = {
        'head': mp_pose.PoseLandmark.NOSE,  # Using the nose as the "head" for simplicity  0
        'neck': mp_pose.PoseLandmark.RIGHT_SHOULDER,  # Using the right shoulder to approximate the neck  1
        'right_shoulder': mp_pose.PoseLandmark.RIGHT_SHOULDER,  #2
        'left_shoulder': mp_pose.PoseLandmark.LEFT_SHOULDER,    #3
        'right_elbow': mp_pose.PoseLandmark.RIGHT_ELBOW,        #4
        'left_elbow': mp_pose.PoseLandmark.LEFT_ELBOW,          #5
        'right_hand': mp_pose.PoseLandmark.RIGHT_WRIST,         #6
        'left_hand': mp_pose.PoseLandmark.LEFT_WRIST,           #7
        'right_hip': mp_pose.PoseLandmark.RIGHT_HIP,            #8
        'left_hip': mp_pose.PoseLandmark.LEFT_HIP,              #9
        'right_knee': mp_pose.PoseLandmark.RIGHT_KNEE,          #10
        'left_knee': mp_pose.PoseLandmark.LEFT_KNEE,            #11
        'right_foot': mp_pose.PoseLandmark.RIGHT_ANKLE,         #12
        'left_foot': mp_pose.PoseLandmark.LEFT_ANKLE,           #13
        'left_heel': mp_pose.PoseLandmark.LEFT_HEEL,            #14
        'right_heel': mp_pose.PoseLandmark.RIGHT_HEEL,          #15
        'left_foot_index': mp_pose.PoseLandmark.LEFT_FOOT_INDEX,#16
        'right_foot_index': mp_pose.PoseLandmark.RIGHT_FOOT_INDEX#17
}


 

def calculate_midpoint(point1, point2):
    """
    Calculate the midpoint between two 3D points.
    :param point1: (x, y, z) coordinates of the first point
    :param point2: (x, y, z) coordinates of the second point
    :return: (x, y, z) midpoint
    """
    midpoint = [(point1[0] + point2[0]) / 2, 
                (point1[1] + point2[1]) / 2, 
                (point1[2] + point2[2]) / 2]
    return midpoint
def calculate_angle_3d(point1, point2, point3):
    """
    Calculate the angle between the vectors (point1 -> point2) and (point2 -> point3).
    All points are in 3D (x, y, z).
    """
    # Create vectors
    vector1 = np.array(point1) - np.array(point2)
    vector2 = np.array(point3) - np.array(point2)
    
    # Normalize the vectors
    vector1_norm = vector1 / np.linalg.norm(vector1)
    vector2_norm = vector2 / np.linalg.norm(vector2)
    
    # Dot product and angle calculation
    dot_product = np.dot(vector1_norm, vector2_norm)
    
    # Clip to avoid numerical errors outside the [-1, 1] range
    dot_product = np.clip(dot_product, -1.0, 1.0)
    
    # Return the angle in degrees
    angle = np.degrees(np.arccos(dot_product))
    
    return angle


def get_all_angles_from_18x3(keypoints_3d):
    """
    Function to compute angles for 18 keypoints in an 18x3 array format.
    :param keypoints_3d: A numpy array of shape (18, 3) where each row contains (x, y, z) coordinates of a keypoint.
    :return: An array of 18 angles corresponding to the keypoints
    """
    angles = []

    # # Define joint triplets for which to calculate angles
    # joint_triplets = [
    #     (1, 2, 4),  # Neck -> Right Shoulder -> Right Elbow
    #     (2, 4, 6),  # Right Shoulder -> Right Elbow -> Right Hand  --right elbow
    #     (1, 3, 5),  # Neck -> Left Shoulder -> Left Elbow
    #     (3, 5, 7),  # Left Shoulder -> Left Elbow -> Left Hand    --leftelbow
    #     (4, 2, 3),  # Right Shoulder -> Neck -> Left Shoulder
    #     (9, 4, 6),  # Right Hip -> Right Shoulder -> Right Elbow   --right-shoulder
    #     (8, 3, 5),  # Left Hip -> Left Shoulder -> Left Elbow      --left-shoulder
    #     (9, 10, 12),  # Right Hip -> Right Knee -> Right Foot      --right -knee
    #     (8, 11, 13),  # Left Hip -> Left Knee -> Left Foot         --left -knee
    #     (10, 12, 17),  # Right Knee -> Right Foot -> Right Foot Index
    #     (11, 13, 16),  # Left Knee -> Left Foot -> Left Foot Index
    #     (4, 9, 10),  # Right Shoulder -> Right Hip -> Right Knee
    #     (3, 8, 11),  # Left Shoulder -> Left Hip -> Left Knee
    #     (1, 9, 10),  # Neck -> Right Hip -> Right Knee
    #     (1, 8, 11),  # Neck -> Left Hip -> Left Knee
    #     (12, 14, 17),  # Right Foot -> Right Heel -> Right Foot Index
    #     (13, 15, 16),  # Left Foot -> Left Heel -> Left Foot Index
    #     (6, 4, 2)  # Right Hand -> Right Elbow -> Right Shoulder
    # ]

     # Define joint triplets for which to calculate angles
    joint_triplets = [
         
        (2, 4, 6),  # Right Shoulder -> Right Elbow -> Right Hand  --right elbow
        
        (3, 5, 7),  # Left Shoulder -> Left Elbow -> Left Hand    --leftelbow
         
        (9, 4, 6),  # Right Hip -> Right Shoulder -> Right Elbow   --right-shoulder
        (8, 3, 5),  # Left Hip -> Left Shoulder -> Left Elbow      --left-shoulder
        (9, 10, 12),  # Right Hip -> Right Knee -> Right Foot      --right -knee
        (8, 11, 13),  # Left Hip -> Left Knee -> Left Foot         --left -knee
        (10,12,17),  #right knee - right  foot - right foot index  --right foot
        (11, 13,16)   #left knee  -  left foot -  left foot index  -- left foot
        
    ]

    # Calculate angles for each joint triplet
    for joint_triplet in joint_triplets:
        joint1_idx, joint2_idx, joint3_idx = joint_triplet
        
        # Extract the points from the 18x3 array
        point1 = keypoints_3d[joint1_idx]
        point2 = keypoints_3d[joint2_idx]
        point3 = keypoints_3d[joint3_idx]

        # Check if any of the points are missing (i.e., None or NaN)
        if np.any(np.isnan(point1)) or np.any(np.isnan(point2)) or np.any(np.isnan(point3)):
            angles.append(None)  # Append None if any keypoint is missing
        else:
            # Calculate and append the angle
            angle = calculate_angle_3d(point1, point2, point3)
            angles.append(angle)
    
    return np.array(angles).reshape(-1, 1)  # Return the angles as an 18x1 array

 


def pixel_to_world_sealibrary(u, v, depth, camera_matrix):
    # Decompose the camera matrix
    fx, fy = camera_matrix[0, 0], camera_matrix[1, 1]
    cx, cy = camera_matrix[0, 2], camera_matrix[1, 2]

    # Convert pixel (u, v) and depth Z to world coordinates (X, Y, Z)
    X = (u - cx) * depth / fx
    Y = (v - cy) * depth / fy
    Z = depth

    return np.array([X, Y, Z])

 


# it is use keypoint process

def return_BOS_vectors_singlekeypoint(tvec_var, rvec_var, tvec_ref, rvec_ref, keypoints_var):
    """
    Transforms keypoints from the variable board frame to the reference board frame.

    Parameters:
    - tvec_var: Translation vector for the variable board (shape: (3,))
    - rvec_var: Rotation vector for the variable board (shape: (3,))
    - tvec_ref: Translation vector for the reference board (shape: (3,))
    - rvec_ref: Rotation vector for the reference board (shape: (3,))
    - keypoints_var: Keypoints from the variable board (shape: (23, 3))

    Returns:
    - keypoints_from_ref_board: Transformed keypoints in the reference board frame (shape: (23, 3))
    """
    keypoints_var = np.array(keypoints_var) 

     # Handle input shape (1, 3) or (23, 3)
    if keypoints_var.ndim == 1:
        keypoints_var = keypoints_var.reshape(1, 3)
    
    # Compute rotation matrices
    rot_matrix_ref, _ = cv2.Rodrigues(rvec_ref)
    rot_matrix_var, _ = cv2.Rodrigues(rvec_var)

    tvec_var = tvec_var.reshape(3, 1)
    tvec_ref = tvec_ref.reshape(3, 1)

    relative_translation = tvec_var - tvec_ref
    relative_orientation = np.matmul(np.transpose(rot_matrix_ref), rot_matrix_var)
    trans_var_ref = np.matmul(np.transpose(rot_matrix_ref), relative_translation)

    # Initialize an array for the transformed keypoints
    keypoints_from_ref_board = np.zeros_like(keypoints_var)

    for i in range(keypoints_var.shape[0]):
        keypoint_var = keypoints_var[i].reshape(3, 1)
        keypoint_var_ = np.matmul(np.transpose(rot_matrix_var), (keypoint_var - tvec_var))
        keypoint_var_rot = np.matmul(np.transpose(relative_orientation), keypoint_var_)
        keypoint_from_ref_board = keypoint_var_rot + trans_var_ref
        keypoints_from_ref_board[i] = keypoint_from_ref_board.reshape(1,3)

    return keypoints_from_ref_board

# it is use foot process
def return_BOS_vectors_footprocess(tvec_var,rvec_var,tvec_ref,rvec_ref,input_vector_1,input_vector_2):

    ankle_vector = np.array(input_vector_1).reshape(3,1)

    toe_vector = np.array(input_vector_2).reshape(3,1)
    rot_matrix_ref,_ = cv2.Rodrigues(rvec_ref)
    rot_matrix_var,_ = cv2.Rodrigues(rvec_var)
   
    tvec_var = tvec_var.reshape(3,1) #changing board
    tvec_ref = tvec_ref.reshape(3,1) #reference board

    relative_translation = tvec_var-tvec_ref
    relative_orientation = np.matmul(np.transpose(rot_matrix_ref),rot_matrix_var) 
    trans_var_ref = np.matmul(np.transpose(rot_matrix_ref),(relative_translation))
    # print(f'trans_var_ref : {trans_var_ref}')
   
    

    # this block finds the heel and toe vector with respect to their boards frame
    

    ankle_vector_ = np.matmul(np.transpose(rot_matrix_var),(ankle_vector-tvec_var))
   

    ankle_vector_rot = np.matmul(np.transpose(relative_orientation),ankle_vector_)
   
    ankle_vector_from_ref_board = ankle_vector_rot + trans_var_ref 
   



    toe_vector_ = np.matmul(np.transpose(rot_matrix_var),(toe_vector-tvec_var))
    toe_vector_rot=np.matmul(np.transpose(relative_orientation),toe_vector_)   
    toe_vector_from_ref_board= toe_vector_rot + trans_var_ref


    ankle_vector_from_ref_board = ankle_vector_from_ref_board.reshape(1,3)
    toe_vector_from_ref_board = toe_vector_from_ref_board.reshape(1,3)
    # print(f'ankle vector : {ankle_vector_from_ref_board}')

    return ankle_vector_from_ref_board,toe_vector_from_ref_board



 