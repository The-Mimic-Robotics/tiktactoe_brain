import cv2
import base64
import re
import time
from config import GRID_MAPPING

print("📷 [WARMING UP CAMERA...]")
cap = cv2.VideoCapture(1) 
time.sleep(1.0) # Let the sensor warm up just once at startup

def rotate_and_crop(image, angle, crop_box):
    """Rotates an OpenCV image around its center and crops it."""
    # 1. Rotate
    (h, w) = image.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(image, M, (w, h))
    
    # 2. Crop
    y_start, y_end, x_start, x_end = crop_box
    
    # Safe bounds check to prevent crashes if numbers are too big
    y_start, x_start = max(0, y_start), max(0, x_start)
    y_end, x_end = min(h, y_end), min(w, x_end)
    
    cropped = rotated[y_start:y_end, x_start:x_end]
    return cropped

def encode_image_to_base64(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def capture_board_image(save_path="current_board.png"):
    if not cap.isOpened(): 
        return False

    ret, frame = cap.read()
    if ret:

        frame = rotate_and_crop(frame, -50.0, (150, 480, 300, 600))
        
        frame = cv2.resize(frame, (512,512))

        cv2.imwrite(save_path, frame)
        cap.release()
        return save_path
    cap.release()
    return None


