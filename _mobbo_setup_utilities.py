 
from random import randint
import numpy as np
import keyboard
import cv2
import socket
import keyboard
import time
import math
from local_ip_fetch import*


MESSAGE = "Hey Mobbos!"
local_ip=Ip()

UDP_IP =  local_ip.Local_ip() [0]
 
UDP_PORT = 23000        
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)



def is_between(value, y1, y2):
	if ((y1 > y2 and y1 >= value > y2) or y2 >= value > y1):
		return True
	return False

def calc_intersection(point, side_a, side_b):
   
     m = (side_b[1] - side_a[1]) / (side_b[0] - side_a[0]) 
     x = ((point[1]-side_a[1])/m) + side_a[0]
     y = point[1]
     return (x, y)

 

def led_glow(UDP_IP):
    LED_ON=0X21
    sock.sendto(bytes([LED_ON]),(UDP_IP,23000))
    
def led_off(UDP_IP):
    LED_OFF=0X20
    sock.sendto(bytes([LED_OFF]),(UDP_IP,23000))


def led_glow_up(UDP_IP):
    LED_ON = 0x21
    retries = 3  # Number of retries if the LED doesn't glow

    for attempt in range(retries):
        try:

            sock.sendto(bytes([LED_ON]), (UDP_IP, 23000))
            # print(f"LED_ON command sent to {UDP_IP}")


            try:

                data, _ = sock.recvfrom(1024)  # Receive response from the LED device
                if data == b'ACK':  # Replace with actual acknowledgment response
                    # print(f"LED turned ON confirmed by {UDP_IP}")
                    break  # Exit the loop if the LED turned on successfully
            except socket.timeout:
                print(f"No response from {UDP_IP}, retrying...")

        except Exception as e:
            print(f"Error sending LED_ON command to {UDP_IP}: {e}")
        

        time.sleep(1)

def led_off_down(UDP_IP):
    LED_OFF = 0x20
    retries = 3  # Number of retries if the LED doesn't turn off

    for attempt in range(retries):
        try:

            sock.sendto(bytes([LED_OFF]), (UDP_IP, 23000))
            # print(f"LED_OFF command sent to {UDP_IP}")


            try:
                data, _ = sock.recvfrom(1024)  # Receive response from the LED device
                if data == b'ACK':  # Replace with actual acknowledgment response
                    print(f"LED turned OFF confirmed by {UDP_IP}")
                    break  # Exit the loop if the LED turned off successfully
            except socket.timeout:
                print(f"No response from {UDP_IP}, retrying...")

        except Exception as e:
            print(f"Error sending LED_OFF command to {UDP_IP}: {e}")
        

        time.sleep(1)

def Send_led_commands(addresses, image):

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(2)  # Set timeout for 2 seconds to handle possible delays


    for idx, address in enumerate(addresses):
        try:

            for attempt in range(3):
                led_glow_up(sock, address)
                time.sleep(1)  # Small delay after sending the command



            cv2.imwrite("led_on "+str(address)+".jpg",image)
            print(f"LED turned ON for {address}")


            time.sleep(5)


            for attempt in range(3):
                led_off_down(sock, address)
                time.sleep(1)  # Small delay after sending the command


            print(f"LED turned OFF for {address}")


            time.sleep(1)

        except Exception as e:
            print(f"Error processing {address}: {e}")


    sock.close()


    


def get_available_ids():
     
     
     
    UDP_PORT = 23000           
    MESSAGE = "Hey!mobbos"


    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

     
    sock.settimeout(5)


    unique_addresses = set()


    start_time = time.time()
    while time.time() - start_time < 3:

        sock.sendto(MESSAGE.encode(), (UDP_IP, UDP_PORT))
        
        try:

            data, addr = sock.recvfrom(1024)
            

            if addr not in unique_addresses:
                unique_addresses.add(addr)
        except socket.timeout:
            break  # Break the loop if a timeout occurs


    list_of_addresses = [addr[0] for addr in unique_addresses]

    
    sock.close()
    if not list_of_addresses:
        print("No addresses found!")
         
        return None   

    return list_of_addresses

def distance(point1, point2):
    """Calculate Euclidean distance between two points."""
    return math.sqrt((point1[0] - point2[0]) ** 2 + (point1[1] - point2[1]) ** 2)

def rotation_matrix_to_euler(rotation_matrix):
    return cv2.RQDecomp3x3(rotation_matrix)[0]

def is_white(pixel):

    return pixel[0] > 200 and pixel[1] > 200 and pixel[2] > 200

def convert_to_quadrilaterals(a):
    quadrilaterals = []
    for array in a:
        quadrilateral = [(x, y) for x, y in array]
        quadrilaterals.append(quadrilateral)
    return quadrilaterals

if __name__ =="__main__":
    stand=get_available_ids()
    print(stand)