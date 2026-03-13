import os
import time
import base64
import cv2
import pygame
import threading
import sys
import tty
import termios
import socket
import re
import speech_recognition as sr
from openai import OpenAI


TTS_UDP_IP = "127.0.0.1"
TTS_UDP_PORT = 5006
tts_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


# --- UDP Configuration ---
UDP_IP = "127.0.0.1" # Change to the robot computer's IP if running on separate machines
UDP_PORT = 5005
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


client = OpenAI(api_key="")

# --- Configuration ---
GRID_MAPPING = """
Here are the valid and strict board positions and their corresponding IDs:
       Red X:
       1: bottom left | 2: bottom middle | 3: bottom right
       4: middle left | 5: center        | 6: middle right
       7: top left    | 8: top middle    | 9: top right

       Blue O:
       10: bottom left | 11: bottom middle | 12: bottom right
       13: middle left | 14: center        | 15: middle right
       16: top left    | 17: top middle    | 18: top right
"""



# We need a lock so the game loop and background chat don't talk at the exact same time
audio_lock = threading.Lock()
chatter_muted = threading.Event()  # This will allow us to mute the background chatter when the robot is taking its turn

# ==========================================
# 1. SHARED VOICE MODULE
# ==========================================

def get_single_keypress():
    """Reads a single keypress from the Linux terminal without needing Enter."""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        # setcbreak allows us to read one char at a time without Enter
        tty.setcbreak(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch

# def speak(text):
#     """Converts text to speech and plays it safely across threads."""
#     with audio_lock:  # This ensures only one thread can use the speakers at a time
#         print(f"\nMimic says: {text}")
        
#         # Use a unique timestamp for the file so threads don't overwrite each other
#         speech_file = f"temp_voice_{int(time.time())}.mp3" 
        
#         try:
#             with client.audio.speech.with_streaming_response.create(
#                 model="tts-1-hd",
#                 voice="nova",
#                 input=text
#             ) as response:
#                 response.stream_to_file(speech_file)

#             pygame.mixer.init()
#             pygame.mixer.music.load(speech_file)
#             pygame.mixer.music.play()
            
#             while pygame.mixer.music.get_busy():
#                 pygame.time.Clock().tick(10)
                
#             pygame.mixer.quit()
#         except Exception as e:
#             print(f"Voice error: {e}")
#         finally:
#             if os.path.exists(speech_file):
#                 os.remove(speech_file)


def speak(text):
    """Sends text over UDP to the local Coqui XTTSv2 server."""
    with audio_lock:  
        print(f"\nMimic says: {text}")
        try:
            # Send the text to our dedicated TTS GPU server
            tts_sock.sendto(text.encode('utf-8'), (TTS_UDP_IP, TTS_UDP_PORT))
            
            # Add a slight delay just so the print statements in the terminal don't outrun the audio
            time.sleep(1) 
        except Exception as e:
            print(f"Failed to send text to TTS server: {e}")


# ==========================================
# 2. BACKGROUND CHAT THREAD (From chatter.py)
# ==========================================
def background_conversation_loop():
    """This runs continuously in the background to handle casual conversation."""
    recognizer = sr.Recognizer()
    
    with sr.Microphone() as source:
        # Adjust for ambient noise just once when the thread starts
        recognizer.adjust_for_ambient_noise(source, duration=1) 
        
        while True:

            # --- NEW MUTE CHECK ---
            if chatter_muted.is_set():
                time.sleep(0.5) # Sleep briefly so we don't fry the CPU
                continue        # Skip the rest of the loop and check again
            # ----------------------

            try:
                # Listen for speech
                audio_data = recognizer.listen(source, timeout=5, phrase_time_limit=10)
                
                with open("temp_input.wav", "wb") as f:
                    f.write(audio_data.get_wav_data())

                # STT
                with open("temp_input.wav", "rb") as audio_file:
                    transcription = client.audio.transcriptions.create(
                        model="whisper-1", 
                        file=audio_file
                    )
                user_text = transcription.text
                
                if not user_text.strip():
                    continue
                    
                print(f"\n[Heard in background]: {user_text}")

                # LLM
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "You are Mimic, a bimanual robot playing tic-tac-toe. Keep casual conversation to 1-2 short sentences. Be witty."},
                        {"role": "user", "content": user_text}
                    ]
                )
                ai_text = response.choices[0].message.content
                
                # Speak the response
                speak(ai_text)

            except sr.WaitTimeoutError:
                continue
            except Exception as e:
                pass # Fail silently in the background so it doesn't crash the game

# ==========================================
# 3. VISION MODULE (From thinker.py)
# ==========================================

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

def capture_board_image(save_path="current_board.png"):
    cap = cv2.VideoCapture(8) 
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

def encode_image_to_base64(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def get_next_move_from_image(image_path, current_player_piece, current_player_color):
    base64_image = encode_image_to_base64(image_path)
    
    # Updated prompt to force Chain of Thought reasoning
    system_prompt = f"""
    You are a strategic Tic-Tac-Toe AI. You play as '{current_player_color}' '{current_player_piece}'.
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

# ==========================================
# 4. MAIN GAME LOOP
# ==========================================
def main():
    # 1. Start the Background Ear/Mouth Thread
    chat_thread = threading.Thread(target=background_conversation_loop, daemon=True)
    chat_thread.start()

    # 2. Setup Robot Game Variables
    TURN_PIECE = "X"
    TURN_COLOR = "Red"
    image_filename = "current_board.png"

    speak("Hello! I am Mimic, your bimanual robotic opponent. Let's play a game of Tic-Tac-Toe. So put that stupid vape aside and BREATH AIR ! Come on loser lets do it!")


    def toggle_mute():
        if chatter_muted.is_set():
            chatter_muted.clear()
            print("\n🟢 [Chatter Bot is UNMUTED]")
        else:
            chatter_muted.set()
            print("\n🔴 [Chatter Bot is MUTED]")

    

    # 3. Main Foreground Loop
    # 3. Main Foreground Loop
    while True:
        # Print the prompt (flush=True forces it to display instantly without a newline)
        print("\n[PRESS ENTER FOR ROBOT TURN] | 'm' to mute | 'q' to quit: ", end="", flush=True)
        
        # This will wait here until EXACTLY one key is pressed
        user_key = get_single_keypress()
        
        if user_key.lower() == 'q':
            speak("Thanks for playing. Shutting down systems.")
            break

        # --- MUTE TOGGLE LOGIC ---
        if user_key.lower() == 'm':
            if chatter_muted.is_set():
                chatter_muted.clear() # Turn the switch OFF (Unmuted)
                print("\n🟢 [Chatter Bot is UNMUTED]")
                speak("My ears are open.")
            else:
                chatter_muted.set()   # Turn the switch ON (Muted)
                print("\n🔴 [Chatter Bot is MUTED]")
            continue # Go back to the start of the loop
        # -------------------------

        # Check for Enter key (which registers as a newline/return character)
        if user_key == '\n' or user_key == '\r':
            # speak("Taking a look at the board.")
            captured_file = capture_board_image(image_filename)

            if captured_file:
                robot_command = get_next_move_from_image(captured_file, TURN_PIECE, TURN_COLOR)

                if robot_command:
                    print("\n========================================")
                    print(f"🤖 COMMAND FOR LE-ROBOT LOOP:")
                    print(f">>> Move ID: {robot_command} <<<")
                    print("========================================\n")
                    # speak(f"My turn is complete. {robot_command}")

                    # SEND OVER UDP
                    sock.sendto(robot_command.encode('utf-8'), (UDP_IP, UDP_PORT))
                    
                    # speak(f"My turn is complete. {robot_command}")

                else:
                     speak("I had trouble generating a move. Try again.")
            else:
                 speak("I couldn't see the camera feed.")
        else:
            # If they press any other random key, just ignore it and re-prompt
            continue

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nGame forcefully terminated.")