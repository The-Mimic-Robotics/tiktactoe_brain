import socket
import threading
from openai import OpenAI
from pynput import keyboard
import config
from mimic_voice import MimicVoice
import mimic_vision

# 1. Setup
client = OpenAI(api_key=config.OPENAI_API_KEY)
# Create the conversation object to get an ID
conv = client.conversations.create() 
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# --- FIX: Pass all 3 required arguments here ---
voice = MimicVoice(client, conv.id, sock)

def on_press(key):
    if key == keyboard.Key.space: # Changed to Space to avoid terminal newline spam
        if not voice.ptt_active.is_set():
            voice.ptt_active.set()
    
    elif hasattr(key, 'char') and key.char == 'w':
        sock.sendto("wait".encode('utf-8'), (config.ROBOT_UDP_IP, config.ROBOT_UDP_PORT))
        
    elif hasattr(key, 'char') and key.char == '-':
        sock.sendto("-1".encode('utf-8'), (config.ROBOT_UDP_IP, config.ROBOT_UDP_PORT))

def on_release(key):
    if key == keyboard.Key.space:
        voice.ptt_active.clear()

def main():
    # Start the fused loop that contains your working mic logic
    # This runs in the background so main.py stays responsive
    chat_thread = threading.Thread(target=voice.fused_conversation_loop, daemon=True)
    chat_thread.start()
    
    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()

    voice.speak("Mimic system active. Hold space to talk and show me the board.")
    
    try:
        # Keep the main thread alive
        listener.join()
    except KeyboardInterrupt:
        print("\nShutting down.")

if __name__ == "__main__":
    main()