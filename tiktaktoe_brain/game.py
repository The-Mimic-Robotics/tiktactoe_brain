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
from pynput import keyboard


TTS_UDP_IP = "127.0.0.1"
TTS_UDP_PORT = 5006
tts_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


# --- UDP Configuration ---
UDP_IP = "127.0.0.1" # Change to the robot computer's IP if running on separate machines
UDP_PORT = 5005
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


client = OpenAI(api_key="")

conversation = client.conversations.create()
CONVERSATION_ID = conversation.id

# Use the exact dictionary format from your dashboard example
MIMIC_PROMPT = {
    "id": "pmpt_69b5a72f3b8c819491ad004531919a9b05f7f92fd2ab1d24",
    "version": "1"
}

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

def speak(text):
    """Converts text to speech and plays it safely across threads."""
    with audio_lock:  # This ensures only one thread can use the speakers at a time
        print(f"\nMimic says: {text}")
        
        # Use a unique timestamp for the file so threads don't overwrite each other
        speech_file = f"temp_voice_{int(time.time())}.mp3" 
        
        try:
            with client.audio.speech.with_streaming_response.create(
                model="tts-1-hd",
                voice="nova",
                input=text
            ) as response:
                response.stream_to_file(speech_file)

            pygame.mixer.init()
            pygame.mixer.music.load(speech_file)
            pygame.mixer.music.play()
            
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
                
            pygame.mixer.quit()
        except Exception as e:
            print(f"Voice error: {e}")
        finally:
            if os.path.exists(speech_file):
                os.remove(speech_file)


# def speak(text):
#     """Sends text over UDP to the local Coqui XTTSv2 server."""
#     with audio_lock:  
#         print(f"\nMimic says: {text}")
#         try:
#             # Send the text to our dedicated TTS GPU server
#             tts_sock.sendto(text.encode('utf-8'), (TTS_UDP_IP, TTS_UDP_PORT))
            
#             # Add a slight delay just so the print statements in the terminal don't outrun the audio
#             time.sleep(1) 
#         except Exception as e:
#             print(f"Failed to send text to TTS server: {e}")


# ==========================================
# 2. BACKGROUND CHAT THREAD (From chatter.py)
# ==========================================

ptt_active = threading.Event() # Set when key is held, cleared when released
recording_done = threading.Event() # Used to signal when to process speech


def on_press(key):
    # Change 'space' to 'alt' or any other key you prefer
    if key == keyboard.Key.space:
        if not ptt_active.is_set():
            ptt_active.set()
            print("\n🎤 [LISTENING...]")

def on_release(key):
    if key == keyboard.Key.space:
        ptt_active.clear()
        print("\n⏳ [PROCESSING...]")
        
listener = keyboard.Listener(on_press=on_press, on_release=on_release)
listener.start()

def background_conversation_loop():
    recognizer = sr.Recognizer()
    mic = sr.Microphone()
    
    with mic as source:
        recognizer.adjust_for_ambient_noise(source, duration=1) 
        
        while True:
            # 1. Wait for the user to press the PTT button
            if not ptt_active.is_set():
                time.sleep(0.1)
                continue

            # 2. Record while the button is held
            try:
                # We start a dynamic recording session
                audio_data = None
                
                # This records until the user RELEASES the button OR silence is detected
                # phrase_time_limit ensures it doesn't record forever
                audio_data = recognizer.listen(source, timeout=None, phrase_time_limit=10)
                
                # Check if user is still holding the button; if they released mid-sentence, 
                # recognizer.listen will have already returned the audio.

                with open("temp_input.wav", "wb") as f:
                    f.write(audio_data.get_wav_data())

                # STT Transcription
                with open("temp_input.wav", "rb") as audio_file:
                    transcription = client.audio.transcriptions.create(
                        model="whisper-1", 
                        file=audio_file
                    )
                user_text = transcription.text
                
                if not user_text.strip():
                    continue
                    
                print(f"\n[Heard]: {user_text}")

                # LLM Response
                response = client.responses.create(
                    prompt=MIMIC_PROMPT,
                    conversation=CONVERSATION_ID,
                    input=user_text,
                    store=True
                )
                
                ai_text = response.output_text
                speak(ai_text)

            except Exception as e:
                # If we get a timeout because they clicked but didn't talk, ignore it
                pass

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

    speak("Hello! I am Mimic, your bimanual robotic opponent. Let's play a game of Tic-Tac-Toe.")




    

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

        # 2. SEND COMMAND "0"
        elif user_key == '0':
            print("\n[Sending Command: 0]")
            sock.sendto("0".encode('utf-8'), (UDP_IP, UDP_PORT))
            continue

        # 3. SEND COMMAND "-1"
        elif user_key == '-':
            print("\n[Sending Command: -1]")
            sock.sendto("-1".encode('utf-8'), (UDP_IP, UDP_PORT))
            continue

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
                    #  speak("I had trouble generating a move. Try again.")
                    print("!!!  Couldnt generate the move, please try again   !!!\n")
            else:
                #  speak("I couldn't see the camera feed.")
                print("!!!  CANT SEE CAMERA FEED   !!!\n")
        else:
            # If they press any other random key, just ignore it and re-prompt
            continue

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nGame forcefully terminated.")