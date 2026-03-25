import os
import time
import threading
import pygame
import speech_recognition as sr
from config import MIMIC_PROMPT # Only need the prompt dict here

class MimicVoice:
    def __init__(self, client, conversation_id):
        self.client = client
        self.conv_id = conversation_id
        self.audio_lock = threading.Lock()
        self.ptt_active = threading.Event()
        
    def speak(self, text):
        with self.audio_lock:
            print(f"\nMimic says: {text}")
            speech_file = f"temp_voice_{int(time.time())}.mp3"
            try:
                # Use self.client
                with self.client.audio.speech.with_streaming_response.create(
                    model="tts-1-hd", voice="nova", input=text
                ) as response:
                    response.stream_to_file(speech_file)
                
                pygame.mixer.init()
                pygame.mixer.music.load(speech_file)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    pygame.time.Clock().tick(10)
                pygame.mixer.quit()
            finally:
                if os.path.exists(speech_file): os.remove(speech_file)

    def conversation_loop(self):
        recognizer = sr.Recognizer()
        # Use your Bluetooth index here
        mic = sr.Microphone(device_index=14, sample_rate=16000) 

        print("🎤 [SYSTEM READY] - Press Space to talk.")

        while True:
            # 1. Use self.ptt_active
            if not self.ptt_active.is_set():
                time.sleep(0.01)
                continue

            print("🎤 [LISTENING...]")
            audio_chunks = []
            
            with mic as source:
                while self.ptt_active.is_set():
                    try:
                        chunk = mic.stream.read(mic.CHUNK)
                        audio_chunks.append(chunk)
                    except IOError:
                        pass
            
            print("⏳ [PROCESSING...]")

            if audio_chunks:
                byte_data = b"".join(audio_chunks)
                audio_data = sr.AudioData(byte_data, 16000, 2)
                
                try:
                    with open("temp_input.wav", "wb") as f:
                        f.write(audio_data.get_wav_data())

                    with open("temp_input.wav", "rb") as audio_file:
                        transcription = self.client.audio.transcriptions.create(
                            model="whisper-1",
                            file=audio_file
                        )
                    
                    user_text = transcription.text.strip()
                    if user_text:
                        print(f"\n[Heard]: {user_text}")
                        # Use self.client and self.conv_id
                        response = self.client.responses.create(
                            prompt=MIMIC_PROMPT,
                            conversation=self.conv_id,
                            input=user_text,
                            store=True
                        )
                        self.speak(response.output_text)

                except Exception as e:
                    print(f"Transcription error: {e}")