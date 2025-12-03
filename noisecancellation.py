
# the noise of keypoints process to neglate 
# it is use in function of keypoints



import numpy as np
import matplotlib.pyplot as plt
from collections import deque
import cv2

# Initialize a buffer for storing the last N keypoints
BUFFER_SIZE = 10
data_buffer = deque(maxlen=BUFFER_SIZE)

def update_buffer(new_keypoints):
    """
    Update the buffer with new keypoints, replacing (0,0,0) with the mean of non-zero points
    for each specific keypoint.
    """
    # Add new keypoints to the buffer
    data_buffer.append(new_keypoints)
    
    # Convert buffer to numpy array for easy processing
    buffer_array = np.array(data_buffer)  # Shape (BUFFER_SIZE, 14, 3)

    # Initialize the mean_values array with zeros
    mean_values = np.zeros((18, 3))
    
    # Loop through each keypoint (14 keypoints in total)
    for i in range(18):
        # Extract all instances of this keypoint across the buffer
        keypoint_history = buffer_array[:, i, :]  # Shape (BUFFER_SIZE, 3)
        
        # Filter out rows where the keypoint is (0,0,0)
        non_zero_keypoints = keypoint_history[np.any(keypoint_history != 0, axis=1)]
        
        # Calculate mean of non-zero keypoints if available
        if len(non_zero_keypoints) > 0:
            mean_values[i] = np.mean(non_zero_keypoints, axis=0)
        else:
            mean_values[i] = np.zeros(3)  # Keep (0,0,0) if no valid points
    
    # Replace only the (0,0,0) points in new_keypoints with the corresponding mean value
    corrected_data = np.where(new_keypoints == 0, mean_values, new_keypoints)
    
    # Update the buffer with corrected data
    data_buffer[-1] = corrected_data
    
    return corrected_data

 

 
