import numpy as np
import threading    
import cv2
from aruco_realsense import *
from ultralytics import YOLO
import pyrealsense2 as rs  # Ensure this is imported
from Frame_Process import*
import time

ARUCO_DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_ARUCO_ORIGINAL)
ARUCO_PARAMETERS = cv2.aruco.DetectorParameters()
DETECTOR = cv2.aruco.ArucoDetector(ARUCO_DICT, ARUCO_PARAMETERS)
MARKER_LENGTH = 0.304
MARKER_SEPARATION = 0.043

foot_thread_flag=True

class foot_detector():
   
    def __init__(self):
        # self.target_ids = [44, 88, 11, 68]
        self.target_ids = [11, 68]
        # self.foot_predict = YOLO(r"E:\OpenCV_mobbo_works\mobbo_3d_env_full_version\300_3points_foot_model_6thmarch\weights\best.pt") for three point model
        self.foot_predict = YOLO(r"E:\OpenCV_mobbo_works\BaseOfSupport\notebooks\runs\pose\mannually annotated line foot YOLO_Model\weights\best.pt")
        self.keypoints = None
        self.combained_keypoint={}
        self.data=None
        self.depth = None
        self.image=None
        
        

    def start_detection(self,frame2):
        global foot_thread_flag
        foot_thread_flag=True
        self.thread = threading.Thread(target=self.detect_foot, args=(1280, 720, MAT, DIST,self. target_ids,frame2))
        # self.thread.daemon = True  # Ensure thread exits with main program
        self.thread.start()

    def foot_prediction_stopthread(self):
        # print("THE CLICK THE STOP FOOT")
        global foot_thread_flag
        foot_thread_flag=False
        # print("the false condition")
        # if self.thread is not None:
        #     self.thread.join()
        #     print("the foot thread is stop")

    def get_keypoints(self):
        return self.keypoints,self.depth,self.image
        # return self.keypoints 

    def detect_foot(self, w, h, mat, dist, target_ids,frame2):

        
           
        # print("the detect foot script is start")
        # pipeline = initialize_pipeline(w, h)
        # align = rs.align(rs.stream.color)

        corners_board = np.array([
            [0.35, 0.35, 0.0],
            [-0.35, 0.35, 0.0],
            [-0.35, -0.35, 0.0],
            [0.35, -0.35, 0.0]
        ], dtype=np.float32).reshape(-1, 1, 3)

        frame_count = 0
        stored_rvecs = {}
        stored_tvecs = {}
        detected_ids = set(target_ids)  # Initialize with target IDs

        while  True:

            if not foot_thread_flag:
                break

            
            color_frame,depth_frame=frame2.get_Frames()
    
            # Check if the frames are None or empty
            if color_frame is None or depth_frame is None or color_frame.size == 0 or depth_frame.size == 0:
                print(" Warning: Empty frame received, retrying...")
                time.sleep(0.1)
                continue  # Skip this iteration and retry

            color_image = color_frame.copy()
            self.depth = depth_frame
            self.image = color_image
                

            # Detect ArUco markers
            corners, ids, rejectedPoints = cv2.aruco.detectMarkers(color_image, ARUCO_DICT)

            # Increment the frame count
            frame_count += 1

            # Check if we're in the first 10 frames
            if frame_count <= 10 and ids is not None:
                # Save detected IDs for future reference
                detected_ids.update(ids.flatten())

                # Estimate pose and store rvec and tvec for each detected marker
                rotation_vectors, translation_vectors = estimate_pose_single_markers(corners, MARKER_POINTS, mat, dist)
                if rotation_vectors is not None and translation_vectors is not None:
                    for i, marker_id in enumerate(ids.flatten()):
                        if marker_id in target_ids:
                            stored_rvecs[marker_id] = rotation_vectors[i]
                            stored_tvecs[marker_id] = translation_vectors[i]

            # After 10 frames, use the detected_ids to continue processing
            elif frame_count > 10 and detected_ids:
                # _img = color_image.copy()

                # If there are stored rvecs and tvecs
                if ids is not None:
                    valid_indices = [i for i, marker_id in enumerate(ids.flatten()) if marker_id in detected_ids]

                    if valid_indices:
                        valid_corners = [corners[i] for i in valid_indices]
                        rotation_vectors, translation_vectors = estimate_pose_single_markers(valid_corners, MARKER_POINTS, mat, dist)

                        # Update stored rvecs and tvecs for the valid detected IDs
                        for i, marker_id in enumerate(ids.flatten()[valid_indices]):
                            stored_rvecs[marker_id] = rotation_vectors[i]
                            stored_tvecs[marker_id] = translation_vectors[i]

                # Iterate through stored rvecs and tvecs for the detected ArUco markers
                for marker_id in stored_rvecs.keys():
                    if marker_id in target_ids:  # Process only the stored detected IDs
                        # Use stored rvec and tvec for this marker
                        rvec = stored_rvecs[marker_id]
                        tvec = stored_tvecs[marker_id]

                        # Project the 3D points using stored rvec and tvec
                        projected_points, _ = cv2.projectPoints(corners_board, rvec, tvec, mat, dist)
                        projected_points = projected_points.astype(int)

                        # Calculate min and max for x and y coordinates
                        x_min = max(0, min(point[0][0] for point in projected_points))
                        x_max = min(color_image.shape[1], max(point[0][0] for point in projected_points))
                        y_min = max(0, min(point[0][1] for point in projected_points))
                        y_max = min(color_image.shape[0], max(point[0][1] for point in projected_points))

                        # Crop and resize the image for this specific marker
                        cropped_frame = color_image[y_min:y_max, x_min:x_max]
                        resized_frame = cv2.resize(cropped_frame, (640, 480))
                         
                        # Make predictions using the foot_predict model
                        results = self.foot_predict.predict(resized_frame, conf=0.5, verbose=False)[0]


                        def normalize_to_pixel(xy_norm, xmin, xmax, ymin, ymax):
                            x_pixel = int(xmin + xy_norm[0] * (xmax - xmin))
                            y_pixel = int(ymin + xy_norm[1] * (ymax - ymin))
                            return x_pixel, y_pixel
                                        
                        
                        # x_norm = results.keypoints.xyn.cpu().numpy()
                    #     x_norm = results.keypoints.xyn.cpu() .numpy()   starts here
                    #     if self.keypoints is None:
                    #         self.keypoints = {}
                        
                    #     if x_norm.shape == (2, 3, 2):  # Two keypoints detected (e.g., two feet)
                    #         self.keypoints.update({
                    #             "right_top": normalize_to_pixel(x_norm[0][1], x_min, x_max, y_min, y_max),
                    #             "right_bottom": normalize_to_pixel(x_norm[0][0], x_min, x_max, y_min, y_max),
                    #             "left_top": normalize_to_pixel(x_norm[1][1], x_min, x_max, y_min, y_max),
                    #             "left_bottom": normalize_to_pixel(x_norm[1][0], x_min, x_max, y_min, y_max),
                    #             "right_side" :normalize_to_pixel(x_norm[0][2], x_min, x_max, y_min, y_max),
                    #             "left_side" :normalize_to_pixel(x_norm[1][2], x_min, x_max, y_min, y_max)
                    #         })

                    # elif x_norm.shape == (1, 3, 2):  # Single keypoint detected (one foot)
                    #     # Temporary dictionary to hold current keypoint
                    #     combined_keypoint = {}

                    #     # Process based on class (0 = Right Foot, 1 = Left Foot)
                    #     if results.boxes.cls.cpu()[0] == 0:  # Class 0: Right foot
                    #         combined_keypoint["right_top"] = normalize_to_pixel(x_norm[0][1], x_min, x_max, y_min, y_max)
                    #         combined_keypoint["right_bottom"] = normalize_to_pixel(x_norm[0][0], x_min, x_max, y_min, y_max)
                    #         combined_keypoint["right_side"] = normalize_to_pixel(x_norm[0][2], x_min, x_max, y_min, y_max)


                    #     elif results.boxes.cls.cpu()[0] == 1:  # Class 1: Left foot
                    #         combined_keypoint["left_top"] = normalize_to_pixel(x_norm[0][1], x_min, x_max, y_min, y_max)
                    #         combined_keypoint["left_bottom"] = normalize_to_pixel(x_norm[0][0], x_min, x_max, y_min, y_max)
                    #         combined_keypoint["left_side"] = normalize_to_pixel(x_norm[0][2], x_min, x_max, y_min, y_max)

                    #     # Update the main keypoints dictionary
                    #     self.keypoints.update(combined_keypoint)
                    #adjustment started
                    foot_parts = ["bottom", "top"]  # Keypoint order from YOLO (adjust if needed)

                    x_norm = results.keypoints.xyn.cpu().numpy()
                    _cls = results.boxes.cls.cpu().numpy()

                    if self.keypoints is None:
                        self.keypoints = {}

                    # Handling two detections
                    if x_norm.shape == (2, 2, 2):  # Two feet detected
                        # Determine which detection is likely left/right
                        if _cls[0] == 0:  # First is right
                            _sides = ["right", "left"]
                        else:
                            _sides = ["left", "right"]

                        for i, side in enumerate(_sides):
                            for j, part in enumerate(foot_parts):
                                x, y = normalize_to_pixel(x_norm[i][j], x_min, x_max, y_min, y_max)
                                self.keypoints[f"{side}_{part}"] = (x, y)

                    # Handling one foot detection
                    elif x_norm.shape == (1, 2, 2):
                        side = "right" if _cls[0] == 0 else "left"
                        for j, part in enumerate(foot_parts):
                            x, y = normalize_to_pixel(x_norm[0][j], x_min, x_max, y_min, y_max)
                            self.keypoints[f"{side}_{part}"] = (x, y)

                    else:
                        self.keypoints = None
              
                

                    if self.keypoints:
                            for key, point in self.keypoints.items():
                                if key == "right_top":
                                    cv2.circle(color_image, point, radius= 3, color=(0,255,0), thickness=-1) # right is blue
                                elif key == "right_bottom":
                                    cv2.circle(color_image, point, radius= 3, color=(0,255,0), thickness=-1)
                                elif key == "right_side":
                                    cv2.circle(color_image, point, radius= 3, color=(0,255,0), thickness=-1)
                                elif key == "left_top":
                                    cv2.circle(color_image, point, radius= 3, color=(0,0,255), thickness=-1) # left is red
                                elif key == "left_bottom":
                                    cv2.circle(color_image, point, radius= 3, color=(0,0,255), thickness=-1)
                                elif key == "left_side":
                                    cv2.circle(color_image, point, radius= 3, color=(0,0,255), thickness=-1)
                
                        
                 
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
      
        # frame2.stop()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    # target_marker_ids = [11, 68]  # Example list of target marker IDs

    frame = Frame_Process()
    frame_thread = threading.Thread(target= frame.run_frame, args=(1280, 720))
    frame_thread.start()
    time.sleep(1)
    predict = foot_detector()
    # predict.detect_foot(1280, 720, MAT, DIST, target_marker_ids)
    predict.start_detection(frame)
    # print("Final keypoints:", predict.get_keypoints())
