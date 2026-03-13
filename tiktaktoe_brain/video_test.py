import cv2
import numpy as np

def rotate_and_crop(image, angle, crop_box):
    """
    Rotates an image around its center and then crops it.
    :param image: The input OpenCV image (numpy array)
    :param angle: Float angle in degrees. Negative for clockwise.
    :param crop_box: Tuple (y_start, y_end, x_start, x_end)
    :return: The processed image
    """
    # --- STEP 1: ROTATION ---
    # Get image dimensions
    (h, w) = image.shape[:2]
    # Find the center point to rotate around
    center = (w // 2, h // 2)

    # Calculate the rotation matrix
    # getRotationMatrix2D takes: (center point, angle, scale factor)
    # Note: A negative angle means clockwise rotation.
    M = cv2.getRotationMatrix2D(center, angle, 1.0)

    # Apply the rotation matrix to the image
    # warpAffine takes: (image, matrix, (final_width, final_height))
    rotated_image = cv2.warpAffine(image, M, (w, h))

    # --- STEP 2: CROPPING ---
    # Unpack cropping coordinates
    # y = rows (up/down), x = columns (left/right)
    y_start, y_end, x_start, x_end = crop_box

    # Ensure coordinates are within bounds (prevents crashing if numbers are off)
    y_start, x_start = max(0, y_start), max(0, x_start)
    y_end, x_end = min(h, y_end), min(w, x_end)

    # Use standard NumPy array slicing to crop
    # Format is image[rows:rows, columns:columns]
    final_image = rotated_image[y_start:y_end, x_start:x_end]

    return rotated_image, final_image

# ==========================================
# TESTING AREA
# ==========================================

# 1. Load your image (replace with an actual captured image path later)
# If you don't have one handy, generate a dummy one for testing:
# dummy_img = np.zeros((480, 640, 3), np.uint8)
# cv2.rectangle(dummy_img, (200, 150), (440, 330), (255, 255, 255), -1) # Draw simulated board area
# cv2.imwrite("test_board.jpg", dummy_img)
raw_image = cv2.imread("current_board.png")  # Replace with "test_board.jpg" if using the dummy image

if raw_image is None:
    print("Error: Could not load image. Make sure 'test_board.jpg' exists.")
    exit()

# === TUNE THESE VALUES ===
# Trial and error is the easiest way to find these initially.

# Angle: Negative = Clockwise, Positive = Counter-Clockwise
ROTATION_ANGLE = -65.0

# Crop Box: (y_top, y_bottom, x_left, x_right)
# Hint: Open the rotated image in GIMP or Paint to find pixel coordinates.
CROP_COORDS = (100, 380, 150, 490) 
# =========================


print("Processing image...")
rotated_view, final_view = rotate_and_crop(raw_image, ROTATION_ANGLE, CROP_COORDS)

# Show results side-by-side (optional, requires GUI)
cv2.imshow("1. Original", raw_image)
cv2.imshow("2. Rotated (Intermediate)", rotated_view)
cv2.imshow("3. Final Cropped Result", final_view)

print("Showing results. Press any key in the windows to exit.")
cv2.waitKey(0)
cv2.destroyAllWindows()

# Save the result to see what the AI will get
cv2.imwrite("cleaned_board_for_ai.png", final_view)