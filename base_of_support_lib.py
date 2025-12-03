import cv2
import numpy as np
from ultralytics import YOLO
import mediapipe as mdp
import pyrealsense2 as rs
from aruco_data import*
import math 




# Initialize MediaPipe Pose
mp_pose = mdp.solutions.pose
pose = mp_pose.Pose(min_detection_confidence=0.7, min_tracking_confidence=0.5)
mp_draw = mdp.solutions.drawing_utils


# # Initialize MediaPipe Pose
# mp_pose = mdp.solutions.pose
# pose = mp_pose.Pose(
#      static_image_mode=False,
#         model_complexity=1,              # Adjust complexity (1 or 2 for higher accuracy, 0 for speed)
#         smooth_landmarks=True,           # Smooth pose landmarks
#         enable_segmentation=True,        # Enable segmentation mask
#         smooth_segmentation=True,        # Smooth segmentation results
#         min_detection_confidence=0.7,    # Minimum detection confidence
#         min_tracking_confidence=0.5      # Minimum tracking confidence
#                      )
# mp_draw = mdp.solutions.drawing_utils




# Load YOLO models for segmentation and pose detection
# model_seg = YOLO("yolov8m-seg.pt")
# model_pose = YOLO("yolov8m-pose.pt")

model_seg = YOLO("yolov8n-seg.pt")
model_pose = YOLO("yolov8n-pose.pt")


# List to store kinematic parameters
initial_keypoint_lengths = []
camera_matrix=RS_CAM_MAT_455   



def pixel_to_world(u, v, depth, camera_matrix):

    fx = camera_matrix[0, 0]
    fy = camera_matrix[1, 1]
    cx = camera_matrix[0, 2]
    cy = camera_matrix[1, 2]
    x = (u - cx) * depth / fx
    y = (v - cy) * depth / fy
    z = depth
    return np.array([x, y, z])



def world_to_pixel(x, y, z, camera_matrix):

    """
    Convert world coordinates to pixel coordinates.

    Args:
    x, y, z: World coordinates.
    camera_matrix: Camera intrinsic matrix.

    Returns:
    (u, v): Pixel coordinates.
    """
    if np.isnan(x) or np.isnan(y) or np.isnan(z) or z == 0:
        return None
    fx = camera_matrix[0, 0]
    fy = camera_matrix[1, 1]
    cx = camera_matrix[0, 2]
    cy = camera_matrix[1, 2]
    
    # Project world coordinates to pixel coordinates
    u = (x * fx / z) + cx
    v = (y * fy / z) + cy
    
    return int(u), int(v)


def get_any_3d_points(u,v,depth_frame,camera_matrix):
    h, w = depth_frame.shape
    rw_point = None
    if 0 <= u < w and 0 <= v < h:  # Boundary check
            depth = depth_frame[v, u] * 0.001  # Convert depth to meters
            rw_point= pixel_to_world(u, v, depth, camera_matrix)
    return rw_point
    



def get_keypoints_3d(landmarks, depth_frame):
    keypoints_3d = {}
 
    h, w = depth_frame.shape

    # Define the keypoints you want to extract
    keypoints = {
        'left_heel': mp_pose.PoseLandmark.LEFT_HEEL,
        'right_heel': mp_pose.PoseLandmark.RIGHT_HEEL,
        'left_foot_index': mp_pose.PoseLandmark.LEFT_FOOT_INDEX,
        'right_foot_index': mp_pose.PoseLandmark.RIGHT_FOOT_INDEX,
        'right_ankle': mp_pose.PoseLandmark.RIGHT_ANKLE,
        'left_ankle': mp_pose.PoseLandmark.LEFT_ANKLE,
        'right_knee': mp_pose.PoseLandmark.RIGHT_KNEE,
        'left_knee': mp_pose.PoseLandmark.LEFT_KNEE
    }

    for name, landmark in keypoints.items():
        u, v = int(landmarks[landmark.value].x * w), int(landmarks[landmark.value].y * h)
      
        if 0 <= u < w and 0 <= v < h:  # Boundary check
            depth = depth_frame[v, u] * 0.001  # Convert depth to meters
            keypoints_3d[name] = pixel_to_world(u, v, depth, camera_matrix)
        else:
            keypoints_3d[name] = None  # Handle out-of-bounds case

    return keypoints_3d


def Return_keypoints_vectors(keypoints_3D):
    if keypoints_3D is None:
        return None, None, None, None, None,None  # Return None for all variables if keypoints_3D is None

    # Original logic to compute right_heel, right_foot_index, left_heel, left_foot_index
    right_ankle = keypoints_3D.get('right_ankle')
    right_foot_index = keypoints_3D.get('right_foot_index')
    left_ankle = keypoints_3D.get('left_ankle')
    left_foot_index = keypoints_3D.get('left_foot_index')
    left_knee = keypoints_3D.get('left_knee')
    right_knee = keypoints_3D.get('right_knee')

    return right_ankle, right_foot_index, left_ankle, left_foot_index, right_knee, left_knee

    
def return_BOS_vectors(tvec_var,rvec_var,tvec_ref,rvec_ref,input_vector_1,input_vector_2):

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
    print(f'ankle vector : {ankle_vector_from_ref_board}')

    return ankle_vector_from_ref_board,toe_vector_from_ref_board
  
def project_vector_3d_to_2d(vector, plane):
    """
    Projects a 3D vector onto a 2D plane defined by a normal vector.

    Parameters:
    vector (numpy.ndarray): A 1x3 array representing the 3D vector to be projected.
    plane (tuple): A tuple containing two vectors defining the plane. The second vector in the tuple is the normal vector of the plane.

    Returns:
    numpy.ndarray: A 1x3 array representing the 2D projection of the input vector onto the plane.
    """
    # Reshape the input vector to a 3x1 column vector
    vector = vector.reshape(3, 1)
    
    # Extract the normal vector of the plane and reshape it to a 3x1 column vector
    ground_vector = plane[1].reshape(3, 1)
    
    # Calculate the scalar projection of the vector onto the normal vector
    nr = np.dot(ground_vector, vector)
    dr = np.dot(ground_vector, ground_vector)
    t = nr / dr
    
    # Calculate the vector component along the normal vector
    projected_vector_normal = t * ground_vector
    
    # Subtract the normal component from the original vector to get the projected vector
    projected_vector = vector - projected_vector_normal
    
    # Reshape the projected vector back to a 1x3 row vector
    projected_vector = projected_vector.reshape(1, 3)
    
    return projected_vector

    
def vector_proj_onto_plane(vector, orthonormal_basis):
    """
    Projects a 3D vector onto a plane defined by an orthonormal basis.

    Parameters:
    vector (numpy.ndarray): A 1x3 array representing the 3D vector to be projected.
    orthonormal_basis (numpy.ndarray): A 2x3 array where each row represents an orthonormal vector defining the plane.

    Returns:
    numpy.ndarray: A 1x3 array representing the projection of the input vector onto the plane.
    """
    # Reshape the orthonormal basis to form the plane matrix
    # print(f'orthonormal_basis : {orthonormal_basis}') #print(orthonormal_basis)
    plane = np.array([orthonormal_basis[0], orthonormal_basis[1]]).reshape(3, 2)
    # print(f'plane : {plane}') #print(plane)
    
    # Calculate the inverse of the plane's Gram matrix
    
    vector=vector.reshape(3,1)
    # Calculate the projection operator
    plane_transpose = np.transpose(plane)
    projection_operator = np.matmul(plane,plane_transpose)
    
    # Project the vector onto the plane
    projected_vector = projection_operator @ vector
    projected_vector=projected_vector.reshape(1,3)
    # print(f'projected_vector : {projected_vector}')
    
    return projected_vector

 




def mask_rectangles(frame, rectangles):
    """
    Masks every pixel inside the given rectangles to white color.

    Parameters:
    frame (numpy.ndarray): The image frame.
    rectangles (list of numpy.ndarray): A list of numpy arrays where each array 
                                        contains the coordinates of a rectangle. 
                                        Example: [array([[x1, y1], [x2, y2], [x3, y3], [x4, y4]])]

    Returns:
    numpy.ndarray: The frame with rectangles masked to white color.
    """
    # Create a copy of the frame to draw the rectangles on
    # masked_frame = frame.copy()
    rectangle=np.array(rectangles)
    
    # Iterate over each set of rectangle points
    
        # Ensure the rectangle points are in integer format
    polygon = np.array(rectangle, dtype=np.int32).reshape((-1, 1, 2))        # Fill the polygon with white color
    # cv2.fillPoly(frame, pts=[polygon], color=(255,255,255))

    return frame



def draw_custom_polyline(frame, pose_landmarks, foot_breadth, foot_length):

    left_ankle_index = mp_pose.PoseLandmark.LEFT_ANKLE.value
    right_ankle_index = mp_pose.PoseLandmark.RIGHT_ANKLE.value
    left_heel_index = mp_pose.PoseLandmark.LEFT_HEEL.value
    right_heel_index = mp_pose.PoseLandmark.RIGHT_HEEL.value
    left_foot_index_index = mp_pose.PoseLandmark.LEFT_FOOT_INDEX.value
    right_foot_index_index = mp_pose.PoseLandmark.RIGHT_FOOT_INDEX.value

    left_heel = np.array([pose_landmarks.landmark[left_heel_index].x, pose_landmarks.landmark[left_heel_index].y])
    right_heel = np.array([pose_landmarks.landmark[right_heel_index].x, pose_landmarks.landmark[right_heel_index].y])
    left_foot_index = np.array([pose_landmarks.landmark[left_foot_index_index].x, pose_landmarks.landmark[left_foot_index_index].y])
    right_foot_index = np.array([pose_landmarks.landmark[right_foot_index_index].x, pose_landmarks.landmark[right_foot_index_index].y])
    # Ensure landmarks are numpy arrays for addition
    left_ankle_index = np.array([pose_landmarks.landmark[left_ankle_index].x, pose_landmarks.landmark[left_ankle_index].y])
    right_ankle_index = np.array([pose_landmarks.landmark[right_ankle_index].x, pose_landmarks.landmark[right_ankle_index].y])

    transaltion_vector_length=world_to_pixel(0,0,foot_length/100, camera_matrix)
    transaltion_vector_breadth=world_to_pixel(foot_breadth/100,0,0, camera_matrix)


    # Define points for the bounding boxes
    left_footpoints = [left_heel,
        left_heel + transaltion_vector_breadth,
        left_foot_index + transaltion_vector_length,
        left_foot_index
      
    ]
    right_footpoints = [
        right_heel,
        right_heel - transaltion_vector_breadth,
        right_foot_index - transaltion_vector_length,
        right_foot_index
        
    ]

    h, w, _ = frame.shape

    # # Convert to pixel coordinates
    left_foot_box = [(int(p[0] * w), int(p[1] * h)) for p in left_footpoints]
    right_foot_box = [(int(p[0] * w), int(p[1] * h)) for p in right_footpoints]

    # # Draw the bounding boxes
    cv2.polylines(frame, [np.array(left_foot_box, np.int32)], isClosed=True, color=(255, 255, 255), thickness=2)
    cv2.polylines(frame, [np.array(right_foot_box, np.int32)], isClosed=True, color=(255, 255, 255), thickness=2)
    # cv2.rectangle(frame, (top_left_x, top_left_y), (bottom_right_x, bottom_right_y), (255, 0, 0), 2)



def draw_foot_boundary(frame, pose_landmarks):

    """ TASK:this block executes the function to draw the foot boundary by 
    drawing a polygon by connecting the heel toe keypoints directly 
    from the RGB video stream in pixelspace

    Parameters:
    frame (numpy.ndarray): The frame to draw the polygon on
    pose_landmarks (mp_pose.Pose): The pose landmarks object

    Returns:
    numpy.ndarray: The frame with the polygon drawn in white
    """

    left_heel_index = mp_pose.PoseLandmark.LEFT_HEEL.value
    right_heel_index = mp_pose.PoseLandmark.RIGHT_HEEL.value
    left_foot_index_index = mp_pose.PoseLandmark.LEFT_FOOT_INDEX.value
    right_foot_index_index = mp_pose.PoseLandmark.RIGHT_FOOT_INDEX.value
    
    points = [
        
        pose_landmarks.landmark[left_heel_index],
        pose_landmarks.landmark[right_heel_index],
        pose_landmarks.landmark[right_foot_index_index],
        pose_landmarks.landmark[left_foot_index_index]
    ]
    
    h, w, _ = frame.shape
    foot_points = [(int(p.x * w), int(p.y * h)) for p in points]
    
    cv2.polylines(frame, [np.array(foot_points, np.int32)], isClosed=True, color=(100, 0, 50), thickness=2)



def convert_to_relative(vector_points, ref_vector,ref_rotation_vector):
    rot_mat,_ = cv2.Rodrigues(ref_rotation_vector)
    rot_mat = rot_mat.reshape(3,3)
    conv_points = []
    for points in vector_points:
        relative_vector_camera = points.reshape(3,1)-ref_vector.reshape(3,1)
        relative_vector_board = np.matmul(np.transpose(rot_mat),relative_vector_camera)
        conv_points.append(relative_vector_board)
    return conv_points
 
def plot_rectangle_3d_points (tvec_var, rvec_var,tvec_ref, r_vec_ref, board_points):
    """    Plots a rectangle on the given axes using the provided vertices.
    
    Parameters:
    ax (matplotlib.axes.Axes): The axes on which to plot the rectangle.
    tvec (np.ndarray): The translation vector.
    rmat (np.ndarray): The rotation matrix for the current board.
    r_mat_ref (np.ndarray): The reference rotation matrix.
    board_points (list): List of 4 tuples containing the vertices of the rectangle in 3D.
    
    Returns:
    matplotlib.patches.Polygon: The polygon patch representing the rectangle.
    """
    # getting the rotation matrices and translation vectors

    rot_mat_ref,_ = cv2.Rodrigues(r_vec_ref)
    rot_mat_var,_ = cv2.Rodrigues(rvec_var)
    tvec_ref = tvec_ref.reshape(3,1)
    tvec_var = tvec_var.reshape(3,1) 

    # relative orientation and translation

    relative_rot_mat = np.matmul(np.transpose(rot_mat_ref),rot_mat_var)
   
    relative_translation_c = tvec_var-tvec_ref


    # Convert the list of board points to a NumPy array

    vertices = np.array(board_points)
    # keypoints_var = np.array(keypoints_var)

    # Handle input shape (1, 3) or (23, 3)
    if vertices.ndim == 1:
        vertices = vertices.reshape(1, 3)
    
    # *************************Transform the vertices to plot it relatively*************************
    # here the transformation are done to plot the board relatively with respect to the first board it is clear that the points where i click on the graph might not properly match due to the translation and the rotation i peformmed.
    vertices_ = []
    for vertex in vertices:
        vertex_local_board= np.matmul(np.transpose(rot_mat_var), (vertex.reshape(3, 1)-tvec_var)) # converting the board vertices with repsect respective board frames using their rot mat from aruco markers
        vertex_relative = np.matmul(np.transpose(relative_rot_mat),vertex_local_board) #now converting the vertex points to the refercne board frame.
        translation_relative = np.matmul(np.transpose(rot_mat_ref),(tvec_var-tvec_ref))# now converting thr translation vector between board 1 and board 2 with respect to ref board frame
        transformed_vertex=vertex_relative+translation_relative # adding up gives the transformed coordinates 
        np.matmul(np.transpose(rot_mat_ref),relative_translation_c.reshape(3, 1))
 
        vertices_.append(transformed_vertex.flatten())


    
    # # Reshape the transformed vertices and take the first two columns (x, y)

    vertices_reshaped = np.array(vertices_)
    
    
    # Create the rectangle polygon
 
    
    return vertices_reshaped

    
def get_rectangle_corners_3d(tvec, rvec, camera_matrix, dist_coeffs, length, breadth):
    """
    Returns the pixel coordinates of the four corners of a rectangle.

    Parameters:
        tvec (np.array): Translation vector obtained from the ArUco marker.
        rvec (np.array): Rotation vector obtained from the ArUco marker.
        length (float): Length of the rectangle in meters. Default is 0.6 (60 cm).
        breadth (float): Breadth of the rectangle in meters. Default is 0.45 (45 cm).
        camera_matrix (np.array): Camera matrix.
        dist_coeffs (np.array): Distortion coefficients.

    Returns:
        np.array: 3D coordinates of the four corners of the rectangle.
    """
    # Define the rectangle in the object coordinate system
    l, b = length / 2, breadth / 2
    object_points = np.array([
        [-l, -b, 0],
        [l, -b, 0],
        [l, b, 0],
        [-l, b, 0]
    ])
    polygon_points, _ = cv2.projectPoints(object_points, rvec, tvec, camera_matrix, dist_coeffs)
    polygon_points_int = np.int32(polygon_points).reshape(-1, 2)
    # for points in polygon_points_int:

    

    rvec_____=rvec
    #Convert the rotation vector to a rotation matrix
    rot_mat, _ = cv2.Rodrigues(rvec_____)

    # Transform the object points to the world coordinate system
    world_points = np.dot(object_points, rot_mat.T) + tvec.T.reshape(-1, 3)
    # print(f'world_points{world_points}')

    return world_points, polygon_points_int
    

def pixels_inside_polygon(image_points, polygon,image):
    """
    Checks if the image points are inside the polygon.

    Parameters:
        image_points (np.array): Pixel coordinates of the image points.
        polygon (np.array): Pixel coordinates of the polygon.

    Returns:
        bool: True if the image points are inside the polygon, False otherwise."""
    image_point = tuple(image_points)
    
    # Convert the polygon points to a NumPy array of type int32
    polygon = np.array(polygon, dtype=np.int32)
    
    # Use cv2.pointPolygonTest to check if the point is inside the polygon
    is_inside = cv2.pointPolygonTest(polygon, image_point, False) >= 0
    
    if is_inside:
        cv2.circle(image, image_point, 5, (0, 255, 0), -1)  # Draw a green circle at the point
    
    return is_inside

# def is_point_in_rectangle_3d(point, rect_points):
#     """
#     Check if a 3D point is inside a rectangle defined by 4 3D points.

#     Parameters:
#         point (np.array): The 3D point to check (shape: (3,)).
#         rect_points (np.array): The 4 corner points of the rectangle (shape: (4, 3)).

#     Returns:
#         bool: True if the point is inside the rectangle, False otherwise.
#     """
#     assert point.shape == (3,), "Point must be a 3D coordinate in the shape (3,)"
#     assert rect_points.shape == (4, 3), "Rectangle points must be in the shape (4, 3)"
#     # Define vectors for the rectangle edges
#     vec0 = rect_points[1] - rect_points[0]
#     vec1 = rect_points[3] - rect_points[0]

#     # Calculate normal vector of the plane
#     normal = np.cross(vec0, vec1)

#     # Project the point onto the plane
#     vec_p = point - rect_points[0]
#     dist_to_plane = np.dot(vec_p, normal) / np.linalg.norm(normal)
#     projection = point - dist_to_plane * normal / np.linalg.norm(normal)

#     # Define vectors for the rectangle edges
#     vec0_norm = vec0 / np.linalg.norm(vec0)
#     vec1_norm = vec1 / np.linalg.norm(vec1)

#     # Calculate projection coordinates
#     proj_vec = projection - rect_points[0]
#     proj_x = np.dot(proj_vec, vec0_norm)
#     proj_y = np.dot(proj_vec, vec1_norm)

#     # Check if projection coordinates are within rectangle boundaries
#     is_inside_rect=0 <= proj_x <= np.linalg.norm(vec0) and 0 <= proj_y <= np.linalg.norm(vec1)
#     # if is_inside_rect:
#     #     cv2.circle(image,world_to_pixel(point,camera_matrix), 5, (0, 255, 0), -1)  # Draw a green circle at the point
    
#     return is_inside_rect





import numpy as np

def is_point_in_rectangle_3d(point, rect_points, tol=1e-6):
    """
    Check if a 3D point's (x, y) coordinates are inside a rectangle defined by 4 corner points.
    
    Parameters:
        point (np.array): The 3D point to check (shape: (3,)).
        rect_points (np.array): The 4 corner points of the rectangle (shape: (4, 3)).
        tol (float): A small tolerance to handle floating-point errors.

    Returns:
        bool: True if the (x, y) point is inside the rectangle, False otherwise.



    """

    print("rect ", rect_points)

    print("point", point)
    assert point.shape == (3,), "Point must be a 3D coordinate in the shape (3,)"
    assert rect_points.shape == (4, 3), "Rectangle points must be in the shape (4, 3)"

    # Convert to 2D (only using x, y)
    point_2d = point[:2]  # Extract (x, y) of the point
    rect_2d = rect_points[:, :2]  # Extract (x, y) of rectangle corners

    # Define vectors for the rectangle edges (in 2D)
    vec0 = rect_2d[1] - rect_2d[0]  # First edge
    vec1 = rect_2d[3] - rect_2d[0]  # Second edge

    # Normalize edge vectors
    vec0_norm = vec0 / np.linalg.norm(vec0)
    vec1_norm = vec1 / np.linalg.norm(vec1)

    # Calculate projection coordinates in 2D rectangle space
    proj_vec = point_2d - rect_2d[0]
    proj_x = np.dot(proj_vec, vec0_norm)
    proj_y = np.dot(proj_vec, vec1_norm)

    # Check if projected point is within rectangle bounds (with tolerance)
    inside_x = -tol <= proj_x <= np.linalg.norm(vec0) + tol
    inside_y = -tol <= proj_y <= np.linalg.norm(vec1) + tol

    is_inside_rect = inside_x and inside_y

    # print(f"Point {point_2d} -> proj_x: {proj_x}, proj_y: {proj_y}, inside_x: {inside_x}, inside_y: {inside_y}")

    return is_inside_rect
