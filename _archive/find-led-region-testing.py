import cv2
import numpy as np
import time

def is_white_vectorized(image):
    """Check if a pixel is white using vectorized operations."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return gray > 200  # Adjust threshold if needed

def rotation_matrix_to_euler(matrix):
    """Convert a rotation matrix to Euler angles."""
    sy = np.sqrt(matrix[0, 0]**2 + matrix[1, 0]**2)
    singular = sy < 1e-6
    if not singular:
        x = np.arctan2(matrix[2, 1], matrix[2, 2])
        y = np.arctan2(-matrix[2, 0], sy)
        z = np.arctan2(matrix[1, 0], matrix[0, 0])
    else:
        x = np.arctan2(-matrix[1, 2], matrix[1, 1])
        y = np.arctan2(-matrix[2, 0], sy)
        z = 0
    return (x, y, z)

def convert_to_quadrilaterals(led_regions):
    """Convert polygon data to quadrilaterals."""
    return [np.array(region, dtype=np.int32) for region in led_regions]

def find_highest_red_intensity_region(image, image_name, polygon):
    """
    Function to check four quadrilateral regions in an image,
    compare their red intensities **after** processing all,
    and return only the highest-intensity region.
    """
    if isinstance(image, str):
        image = cv2.imread(image)
    
    if image is None:
        raise ValueError("Image not loaded properly. Check the file path!")

    start_time = time.time()

    # Validate polygon data
    required_keys = ['board_3dpos', 'rotation_matrices', 'ids', 'led_regions']
    for key in required_keys:
        if key not in polygon or not polygon[key]:
            raise ValueError(f"Missing or empty polygon key: {key}")

    board_pos = polygon['board_3dpos'][0]
    board_rot = polygon['rotation_matrices']
    board_ids = polygon['ids'][0]
    quadrilaterals = convert_to_quadrilaterals(polygon['led_regions'])
    angles = [rotation_matrix_to_euler(rot) for rot in board_rot]

    # Precompute ROI masks
    masks = [
        cv2.fillPoly(np.zeros(image.shape[:2], dtype=np.uint8), [corners], 255)
        for corners in quadrilaterals
    ]

    min_length = min(len(masks), len(board_ids), len(board_pos), len(board_rot))

    threshold = 220  # Adjusted threshold for better detection
    highest_red_intensity = 0
    best_region = None

    intensity_data = []  # Store all regions' intensity

    for i, mask in enumerate(masks):
        if i >= min_length:
            print(f"Skipping mask {i} due to insufficient polygon data.")
            continue

        # Apply mask to extract the region of interest (ROI)
        roi = cv2.bitwise_and(image, image, mask=mask)
        red_channel = roi[:, :, 2]

        # Identify white pixels and high red intensity pixels
        white_mask = is_white_vectorized(roi)
        high_red_mask = (red_channel > threshold) & ~white_mask

        # Compute total red intensity in the region
        total_red_intensity = np.sum(red_channel[high_red_mask])

        print(f"Region {i}: Total Red Intensity = {total_red_intensity}")

        intensity_data.append({
            'index': i,
            'total_red_intensity': total_red_intensity,
            'board_translation': board_pos[i],
            'ip_address': image_name.split("_")[-1].replace(".jpg", ""),
            'angle': angles[i],
            'rotation_matrix': board_rot[i],
            'board_aruco_ids': board_ids[i]
        })

    # After all four loops, find the highest red intensity region
    if intensity_data:
        best_region = max(intensity_data, key=lambda x: x['total_red_intensity'])

    end_time = time.time()
    print(f"Execution time: {end_time - start_time:.5f} seconds")

    if best_region:
        print(f"Region with highest red intensity: {best_region}")
        return [best_region]
    else:
        print("No high red intensity detected in any region.")
        return []
