 
     



import os
import cv2
import time

from _mobbo_setup_utilities import*
from aruco_realsense_related_utils import *

class ImageCaptureManager:
    def __init__(self, base_path="captures_Photo"):
        self.base_path = base_path
        self.current_folder = None
        os.makedirs(self.base_path, exist_ok=True)

    def initialize_folder(self, trial_number):
        """Creates a unique folder for the current trial."""
        if self.current_folder is None:
            timestamp = time.strftime("%Y%m%d-%H%M%S")  # Unique timestamp
            self.current_folder = os.path.join(self.base_path, f'trial_{trial_number}_{timestamp}')
            os.makedirs(self.current_folder, exist_ok=True)
        return self.current_folder

    def clear_folder(self):
        """Deletes all files in the current folder."""
        if self.current_folder and os.path.exists(self.current_folder):
            for file in os.listdir(self.current_folder):
                file_path = os.path.join(self.current_folder, file)
                if os.path.isfile(file_path):
                    os.remove(file_path)
    
    def capture_images(self, pipeline, trial_number):
        """Captures images and stores them in the current folder."""
        start_time_image = time.time()

        # Initialize folder for the trial
        image_folder_path = self.initialize_folder(trial_number)
        image_paths = []
        normal_setup_image=[]
        addresses = get_available_ids()
        print("address IP:", addresses)
        if addresses is  None:
            # if not addresses:
            raise ValueError("No IP found! The devices are not reachable.")

        print(f"Available LEDs: {addresses}")
         

        # Capture and save a "normal setup" image before the LED glow process
        print("Capturing normal setup image...")
        # pipeline.set_exposure(0, auto_exposure=True) 
        # time.sleep(0.5)
        self.polygon=camera_functions(pipeline,mat,dist)
       
        board_pos = self.polygon['board_3dpos'][0]
        board_rot = self.polygon['rotation_matrices']
        board_ids = self.polygon['ids'][0]
        if len(board_ids)!=len(addresses)!=len(board_pos):
            print("board id len=", len(board_ids), "board_pos len=",len(board_pos),"address len=", len(addresses))
            # if not addresses:
            raise ValueError("Some Board or IP not found! The devices are not reachable.")
        pipeline.set_exposure(60, auto_exposure=False) 
        time.sleep(0.5)
        for address in addresses:
            # print(address)
            led_glow(address)  # Turn on the LED
            time.sleep(0.5)
            color_frame, depth_frame = pipeline.get_Frames()  # Capture frames
            if color_frame is None:
                print(f"No color frame for LED {address}. Skipping.")
                continue

            image = color_frame
            image_file = f'image_led_{address}.jpg'
            image_path = os.path.join(image_folder_path, image_file)
            cv2.imwrite(image_path, image)
            image_paths.append(image_path)
            time.sleep(0.3)
            led_off(address)  # Turn off the LED

        pipeline.set_exposure(0, auto_exposure=True) 
        # print(image_paths)
        cv2.destroyAllWindows()
        end_time_captureimage = time.time()
        full_time = end_time_captureimage - start_time_image
        print(f"The camera capture execution time: {full_time:.5f} seconds")

        return image_paths,normal_setup_image,self.polygon

 


if __name__=='__main__':
    ImageCaptureManager.capture_images(1,1,1)





     



