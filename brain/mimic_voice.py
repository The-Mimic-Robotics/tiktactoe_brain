import os
import time
import threading
import pygame
import re
import speech_recognition as sr
import mimic_vision
import config

class MimicVoice:
    def __init__(self, client, conversation_id, sock):
        self.client = client
        self.conv_id = conversation_id
        self.sock = sock 
        self.audio_lock = threading.Lock()
        self.ptt_active = threading.Event()
        
        # This history list provides the 'Context' you wanted
        self.history = [
            {"role": "system", "content": config.FUSED_PROMPT.format(GRID_MAPPING=config.GRID_MAPPING)}
        ]
        
    def speak(self, text):
        with self.audio_lock:
            print(f"\nMimic says: {text}")
            speech_file = f"temp_voice_{int(time.time())}.mp3"
            try:
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

    def fused_conversation_loop(self):
        """KEEPS YOUR WORKING COLD-START MIC LOGIC"""
        recognizer = sr.Recognizer()
        mic = sr.Microphone(device_index=14, sample_rate=16000) 

        print("🎤 [SYSTEM READY] - Hold Space to talk.")

        while True:
            # 1. Wait for PTT trigger from main.py
            if not self.ptt_active.is_set():
                time.sleep(0.01)
                continue

            print("🎤 [LISTENING...]")
            audio_chunks = []
            
            # 2. YOUR WORKING MIC CAPTURE
            with mic as source:
                while self.ptt_active.is_set():
                    try:
                        chunk = mic.stream.read(mic.CHUNK)
                        audio_chunks.append(chunk)
                    except IOError:
                        pass
            
            print("⏳ [PROCESSING VOICE & VISION...]")

            if audio_chunks:
                byte_data = b"".join(audio_chunks)
                audio_data = sr.AudioData(byte_data, 16000, 2)
                
                try:
                    # Save for Whisper
                    with open("temp_input.wav", "wb") as f:
                        f.write(audio_data.get_wav_data())

                    with open("temp_input.wav", "rb") as audio_file:
                        transcription = self.client.audio.transcriptions.create(
                            model="whisper-1", file=audio_file
                        )
                    user_text = transcription.text.strip()
                    if not user_text: continue
                    
                    print(f"\n[Heard]: {user_text}")

                    # --- VISION FUSION ---
                    img_path = mimic_vision.capture_board_image()
                    base64_img = mimic_vision.encode_image_to_base64(img_path)

                    # --- MULTIMODAL BRAIN CALL ---
                    # We add the new message to our history list for context
                    user_msg = {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"User says: {user_text}"},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_img}"}}
                        ]
                    }
                    self.history.append(user_msg)

                    response = self.client.chat.completions.create(
                        model="gpt-4o",
                        messages=self.history,
                        temperature=0.2
                    )

                    ai_output = response.choices[0].message.content
                    self.history.append({"role": "assistant", "content": ai_output})
                    
                    print(f"\n--- AI Brain ---\n{ai_output}\n")

                    # Parse output
                    move_match = re.search(r'<MOVE>(\d+)</MOVE>', ai_output)
                    clean_speech = re.sub(r'<MOVE>.*?</MOVE>', '', ai_output).strip()

                    # Act
                    if clean_speech:
                        self.speak(clean_speech)

                    if move_match:
                        move_id = move_match.group(1)
                        print(f"🤖 SENDING MOVE: {move_id}")
                        self.sock.sendto(move_id.encode(), (config.ROBOT_UDP_IP, config.ROBOT_UDP_PORT))

                except Exception as e:
                    print(f"Fusion Error: {e}")