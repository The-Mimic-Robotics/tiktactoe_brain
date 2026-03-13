import os
os.environ["TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD"] = "1"

import torch
import socket
import pygame
import time
from TTS.api import TTS

# Target a secondary GPU (e.g., cuda:1 for the 3090 Ti or cuda:2 for the 3080 Ti) 
# to keep the 5070 free for the physical robot AI.
DEVICE = "cuda:1" if torch.cuda.device_count() > 1 else "cuda:0"

print(f"Loading XTTSv2 model onto {DEVICE}...")
# This will download the model weights (~2.5GB) the very first time you run it
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(DEVICE)
print("Model loaded and ready!")

# --- UDP Server Configuration ---
UDP_IP = "127.0.0.1"
UDP_PORT = 5006  # Using a different port than your robot movement commands
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))

pygame.mixer.init()
print(f"TTS Server listening on port {UDP_PORT}...")

while True:
    data, addr = sock.recvfrom(4096) # 4096 bytes is plenty for a few sentences of text
    text = data.decode('utf-8').strip()
    
    if text:
        print(f"\n[Synthesizing]: {text}")
        output_file = f"temp_speech_{int(time.time())}.wav"
        
        try:
            # Generate the cloned voice
            tts.tts_to_file(
                text=text, 
                speaker_wav="clone_voice.wav", # Your 3-second reference audio clip
                language="en", 
                file_path=output_file
            )
            
            # Play the generated audio out loud
            pygame.mixer.music.load(output_file)
            pygame.mixer.music.play()
            
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
                
        except Exception as e:
            print(f"Synthesis error: {e}")
        finally:
            # Clean up the audio file after playing
            if os.path.exists(output_file):
                os.remove(output_file)