import socket
import threading
from openai import OpenAI
from pynput import keyboard

import config
from mimic_voice import MimicVoice
import mimic_vision
import utils

# 1. Setup
client = OpenAI(api_key=config.OPENAI_API_KEY)
conv = client.conversations.create()
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

voice = MimicVoice(client, conv.id)

# 2. PTT Keyboard Listeners
def on_press(key):
    if key == keyboard.Key.space:
        voice.ptt_active.set()

def on_release(key):
    if key == keyboard.Key.space:
        voice.ptt_active.clear()

# 3. Execution
def main():
    # Start Voice Thread
    threading.Thread(target=voice.conversation_loop, daemon=True).start()
    
    # Start Keyboard Listener
    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()

    voice.speak("Hello! Let's play.")

    while True:
        print("\n[ENTER] for Robot Turn | [q] quit", end="", flush=True)
        user_key = utils.get_single_keypress()

        if user_key == '\r' or user_key == '\n':
            img = mimic_vision.capture_board_image()
            move = mimic_vision.get_robot_move(client, img, "X", "Red")
            if move:
                print(f"Robot moving to {move}")
                sock.sendto(move.encode(), (config.ROBOT_UDP_IP, config.ROBOT_UDP_PORT))
        
        elif user_key.lower() == 'q':
            break

if __name__ == "__main__":
    main()