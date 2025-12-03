 
import time
from _mobbo_setup_utilities import *
from aruco_realsense_related_utils import *
from datetime import datetime
from  LED_Image_capture import  *
from   Find_led_region import*

class board_pose_estimator():

    def __init__(self):

        self.LED_Process=ImageCaptureManager()
        self.trial_no = 1
         

    def board_pose(self,frame):
        start=time.time()

        frame_instance=frame
     
        self.image_paths,self.setup_image,self.polygon =self.LED_Process.capture_images(frame_instance, self.trial_no )
        
        results = []
        for image_path in self.image_paths:
            image =  image_path
            if image is None:
                print(f"Error: Unable to load image '{image_path}'")
                continue
            
            mean_position = find_high_red_intensity (image, image, self.polygon)
            time.sleep(0.5)
            results.append(mean_position)
 
        return results
    
if __name__ == '__main__':

    mobbo = board_pose_estimator()
    mobbo.board_pose()
