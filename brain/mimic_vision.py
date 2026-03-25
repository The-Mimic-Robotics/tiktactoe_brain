import cv2
import base64
import re
from config import GRID_MAPPING

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
    cap = cv2.VideoCapture(2) 
    if not cap.isOpened(): return False
    
    time.sleep(1.0) 
    ret, frame = cap.read()
    if ret:

        frame= rotate_and_crop(frame, -50.0, (150, 480, 300, 600))

        cv2.imwrite(save_path, frame)
        cap.release()
        return save_path
    cap.release()
    return None


def get_robot_move(client, image_path, piece, color):
    
    if not image_path:
        return None
    
    base64_image = encode_image_to_base64(image_path)
    
    # Updated prompt to force Chain of Thought reasoning
    system_prompt = f"""
    You are a strategic Tic-Tac-Toe AI. You play as '{color}' '{piece}'.
    {GRID_MAPPING}
    
    CRITICAL INSTRUCTIONS:
    1. First, visually scan the board and write out the current 3x3 grid state. Note where the X's and O's are, and which spaces are empty.
    2. Next, write one sentence explaining your strategy. Look for an immediate winning move first. If none, block the opponent from winning. Otherwise, take the center or a corner.
    3. You CANNOT play on a space that is already occupied.
    4. Finally, you MUST output your chosen integer ID inside <MOVE> tags at the very end of your response. 
       Example: <MOVE>6</MOVE>
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Analyze the board and make the best next move."},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}},
                    ],
                }
            ],
            max_tokens=300, # INCREASED so the AI has room to write its thoughts!
            temperature=0.1
        )
        
        # Get the full text response (the "thinking" + the move)
        ai_response = response.choices[0].message.content.strip()
        
        # Print the AI's thought process to your terminal so you can see its logic
        print("\n--- AI Brain ---")
        print(ai_response)
        print("----------------\n")
        
        # Extract just the number inside the <MOVE> tags using Regex
        match = re.search(r'<MOVE>(\d+)</MOVE>', ai_response)
        if match:
            return match.group(1) # Returns just the string number (e.g., "6")
        else:
            print("Error: AI did not format the output with <MOVE> tags.")
            return None
            
    except Exception as e:
        print(f"API Error: {e}")
        return None
    pass