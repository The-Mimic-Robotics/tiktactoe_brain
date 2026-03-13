import os
import base64
from openai import OpenAI
import cv2
import time
import subprocess

# Initialize OpenAI Client
# Ensure OPENAI_API_KEY is set in your environment variables, or paste it here.
client = OpenAI(api_key="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")

# --- Configuration ---
# Define how the AI should understand the board grid.
GRID_MAPPING = """
The board positions are named strictly as follows:
left top    | middle top    | right top
---------------------------------------
left middle | center        | middle right
---------------------------------------
left bottom | bottom middle | right bottom
"""

# Define the strict output format your robot controller needs.
# The AI must fill in the brackets [].
ROBOT_COMMAND_TEMPLATE = "Put [Color] [Piece] at [Position Name]"



def capture_board_image(save_path="current_board.png"):
    """
    Captures a single frame from the camera and saves it to disk.
    """
    # Initialize the camera. 
    # '0' is usually the default webcam (/dev/video0 on Linux).
    # If you are using an external USB camera, it might be 1, 2, etc.
    device_path = "/dev/camera_right_wrist"
    
    # Initialize the camera
    cap = cv2.VideoCapture(device_path)

    if not cap.isOpened():
        print("Error: Could not open the camera. Check your connection.")
        return Falsesrc/mimic/scripts/record_cmd.sh

    # PRO-TIP: Give the camera sensor a moment to adjust its auto-exposure and white balance.
    # Without this, your first frame might be pitch black or blown out.
    print("Waking up camera and adjusting exposure...")
    time.sleep(1.5) 

    # Read the frame
    ret, frame = cap.read()

    if ret:
        # Save the frame to the specified path
        cv2.imwrite(save_path, frame)
        print(f"Success! Board image saved to {save_path}")
        cap.release() # Always release the camera when done!
        return save_path
    else:
        print("Error: Camera opened, but could not read a frame.")
        cap.release()
        return None

def encode_image_to_base64(image_path):
    """Helper: Opens an image file and encodes it into base64 string for OpenAI."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def get_next_move_from_image(image_path, current_player_piece, current_player_color):
    """
    Sends board image to GPT-4o and returns a formatted robot command.
    
    Args:
        image_path (str): Path to the .jpg/.png of the board.
        current_player_piece (str): "X" or "O"
        current_player_color (str): e.g., "Red" or "Blue"
    """
    
    # 1. Encode the image
    base64_image = encode_image_to_base64(image_path)

    # 2. Define the "Brain's" instructions (System Prompt)
    # This is crucial. We must force GPT-4o to stop being chatty and act like a machine.
    system_prompt = f"""
    You are a strategic Tic-Tac-Toe AI engine powering a physical robot.
    Your goal is to win the game. By looking at the provided image of the physical board, analyze the state.
    
    CRITICAL INSTRUCTIONS:
    1. You are currently playing as piece '{current_player_piece}' which is color '{current_player_color}'.
    2. Determine the absolute best next move to win or draw.
    3. {GRID_MAPPING}
    4. OUTPUT FORMAT RULE: You must output ONLY a single command string. Do not provide reasoning, explanations, or markdown.
    5. The output must match this exact template, filling in the bracketed info: {ROBOT_COMMAND_TEMPLATE}
    6. The [Position Name] MUST be exactly one of the phrases from the grid mapping (e.g., 'left top', 'center', 'right bottom'). Do not reverse the words.
    Example valid outputs: "Put Red X at center" or "Put Blue O at right top".
    """

    # 3. Send request to GPT-4o (Multimodal)
    try:
        response = client.chat.completions.create(
            model="gpt-4o", # Must use gpt-4o or gpt-4-turbo for vision capability
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        # The text part of the user prompt
                        {"type": "text", "text": f"It is currently {current_player_color} {current_player_piece}'s turn. What is the next move?"},
                        # The image part of the user prompt
                        {
                            "type": "image_url",
                            "image_url": {
                                # Tell OpenAI it's a base64 jpeg image
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        },
                    ],
                }
            ],
            max_tokens=30, # Keep tokens low since we only expect a short sentence
            temperature=0.1 # Low temperature makes the model more deterministic/strategic
        )
        
        # Extract the clean command string
        robot_command = response.choices[0].message.content.strip()
        return robot_command

    except Exception as e:
        print(f"Error communicating with OpenAI: {e}")
        return None

# ===========================
# Example Usage Simulation
# ===========================
if __name__ == "__main__":
    # --- Simulation Setup ---
    # 1. Assume your camera just saved an image of the board here:
    # (Make sure you actually have an image file at this path to test!)
    image_filename = "current_board.png"
    
    captured_file = capture_board_image(image_filename)

    # 2. Define whose turn it is currently
    TURN_PIECE = "X"
    TURN_COLOR = "Red"
    
    print(f"--- Analyzing board for {TURN_COLOR} {TURN_PIECE}'s turn ---")

    # --- Call the Brain ---
    if captured_file:
        command_for_robot = get_next_move_from_image(captured_file, TURN_PIECE, TURN_COLOR)

        # --- Output Result ---
        if command_for_robot:
            # This print statement represents sending the data to your LeRobot controller
            print(f"\n[SENDING TO ROBOT CONTROLLER]:\n>>> {command_for_robot} <<<")
            
            # try:
            #     result = subprocess.run(
            #         ["./run_robot.sh", command_for_robot], 
            #         check=True,       # Will raise an error if the bash script fails
            #         text=True,        # Captures the terminal output as strings
            #         capture_output=True # Grabs the stdout/stderr so you can print it
            #     )
            #     print("Robot output:", result.stdout)
            # except subprocess.CalledProcessError as e:
            #     print(f"The robot script crashed! Error: {e.stderr}")
                
                
        else:
            print("Failed to generate a move.")

  
