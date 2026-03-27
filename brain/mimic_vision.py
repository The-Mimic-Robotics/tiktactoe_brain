import cv2
import base64
import re
import time
from config import GRID_MAPPING

CAMERA_PATH = "/dev/v4l/by-id/usb-Jieli_Technology_USB_Composite_Device-video-index0"



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
    print("📷 [WARMING UP CAMERA...]")
    cap = cv2.VideoCapture(CAMERA_PATH, cv2.CAP_V4L2) 

    if not cap.isOpened(): 
        print("⚠️ [CAMERA ERROR]: CAMERA HARDWARE NOT FOUND OR BUSY.")
        return False

    try:
        # Minimum warmup: sleep or grab frames
        time.sleep(0.3) 
        
        # Flush the buffer to get a fresh frame
        for _ in range(5):
            cap.grab()

        ret, frame = cap.read()

        if not ret:
            print("⚠️ [CAMERA ERROR]: Unable to capture image.")
            cap.release() # Release if read fails
            return None

        # Processing logic
        frame = rotate_and_crop(frame, -70.0, (200, 480, 200, 500))
        frame = cv2.resize(frame, (512, 512))

        cv2.imwrite(save_path, frame)
        print(f"📸 [CAMERA] Captured and processed")
        
        # Release and return path
        cap.release()
        return save_path

    except Exception as e:
        print(f"⚠️ [IMAGE PROCESSING ERROR]: {e}")
        # Ensure we release the camera even if processing crashes
        if cap.isOpened():
            cap.release()
        return None