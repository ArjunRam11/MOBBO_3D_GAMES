 
import numpy as np
import cv2
import time
from _mobbo_setup_utilities import*


def rotation_matrix_to_euler(rotation_matrix):
    """
    Converts a 3x3 rotation matrix to Euler angles (roll, pitch, yaw).
    """
    return cv2.RQDecomp3x3(rotation_matrix)[0]



def is_white_vectorized(image):
    """
    Vectorized function to check if pixels in an image are white.
    """
    return (image[:, :, 0] > 200) & (image[:, :, 1] > 200) & (image[:, :, 2] > 200)



def find_high_red_intensity(image, image_name, polygon):
    """
    Optimized function to find regions of high red intensity in an image.
    """
    image=cv2.imread(image)
    start_time_red_intensity = time.time()

    # Extract relevant data from polygon
    board_pos = polygon['board_3dpos'][0]
    board_rot = polygon['rotation_matrices']
    board_ids = polygon['ids'][0]

    # print("the board id ",board_ids)
    quadrilaterals = convert_to_quadrilaterals(polygon['led_regions'])

    # Precompute rotation angles
    angles = [rotation_matrix_to_euler(rot) for rot in board_rot]

    # Precompute ROI masks
    masks = [
        cv2.fillPoly(np.zeros(image.shape[:2], dtype=np.uint8), [np.array(corners, dtype=np.int32)], 255)
        for corners in quadrilaterals
    ]

    min_length = min(len(masks), len(board_ids), len(board_pos), len(board_rot))

    threshold = 220
    result_dict = []

    for i, mask in enumerate(masks):
    
 

        if i >= len(board_ids) or i >= len(board_pos) or i >= len(board_rot):
            # print(f"Skipping mask {i} due to insufficient polygon data.")
            continue





        # Apply mask to extract the region of interest (ROI)
        roi = cv2.bitwise_and(image, image, mask=mask)

        # Extract the red channel
        red_channel = roi[:, :, 2]
        
        # Identify white pixels and high red intensity pixels
        white_mask = is_white_vectorized(roi)
        high_red_mask = (red_channel > threshold) & ~white_mask

        # Get coordinates of high red intensity pixels
        y_coords, x_coords = np.where(high_red_mask)
        
        if len(x_coords) > 0:
            mean_x, mean_y = np.mean(x_coords), np.mean(y_coords)  # Calculate mean position
            _address = image_name.split("_")[-1]
            _address=_address.replace(".jpg"," ")
            
            output = (f"[The ArUco with id {board_ids[i]}, "
                       f"The IP address{_address}"
                      f"the 3D position is at {board_pos[i]} and "
                      f"oriented at angle {angles[i]} about the xyz axis with respect to the camera frame.]")
            # print(output)

            result_dict.append({
                'board_translation': board_pos[i],
                'ip_address':_address,
                'angle': angles[i],
                'rotation_matrix': board_rot[i],
                'board_aruco_ids': board_ids[i]
            })
            # time.sleep(0.5)
            

     
    end_time_red_intensity = time.time()
    full_time = end_time_red_intensity - start_time_red_intensity
    print(f"The red intensity execution time: {full_time:.5f} seconds")

    return result_dict


 