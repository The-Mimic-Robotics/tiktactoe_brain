import os
import speech_recognition as sr
import pygame
from openai import OpenAI

# Initialize OpenAI
client = OpenAI(api_key="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")

# Initialize the speech recognizer
recognizer = sr.Recognizer()

def play_audio(file_path):
    """Plays an audio file using Pygame."""
    pygame.mixer.init()
    pygame.mixer.music.load(file_path)
    pygame.mixer.music.play()
    
    # Wait until the audio is finished playing
    while pygame.mixer.music.get_busy():
        pygame.time.Clock().tick(10)
    
    pygame.mixer.quit()
    # Clean up the file after playing
    if os.path.exists(file_path):
        os.remove(file_path)

def voice_chat():
    print("Adjusting for ambient noise... Please wait.")
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=1)
        print("Ready! Speak now...")

        while True:
            try:
                # --- STEP 1: Listen (Microphone Input) ---
                print("\nListening...")
                # This function blocks until it hears silence
                audio_data = recognizer.listen(source, timeout=5, phrase_time_limit=10)
                print("Processing...")

                # Save raw audio to a temporary file for Whisper
                with open("temp_input.wav", "wb") as f:
                    f.write(audio_data.get_wav_data())

                # --- STEP 2: STT (Whisper) ---
                with open("temp_input.wav", "rb") as audio_file:
                    transcription = client.audio.transcriptions.create(
                        model="whisper-1", 
                        file=audio_file
                    )
                user_text = transcription.text
                print(f"You: {user_text}")

                # Optional: Exit command
                if "goodbye" in user_text.lower() or "exit" in user_text.lower():
                    print("Exiting...")
                    break
                
                # --- STEP 3: LLM (GPT-4o) ---
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "You are a robot whos name is mimic and your main feature is that you have 2 arms and can perform some bimanual tasks. Respond in 1-3 sentences (you can also joke and all that)."},
                        {"role": "user", "content": user_text}
                    ]
                )
                ai_text = response.choices[0].message.content
                print(f"AI: {ai_text}")

                # --- STEP 4: TTS (Text-to-Speech) ---
                speech_file = "temp_output.mp3"
                with client.audio.speech.with_streaming_response.create(
                    model="tts-1-hd",
                    voice="nova",
                    input=ai_text
                ) as response:
                    response.stream_to_file(speech_file)

                # --- STEP 5: Play Audio ---
                play_audio(speech_file)

            except sr.WaitTimeoutError:
                # No speech detected, just loop back
                continue
            except Exception as e:
                print(f"An error occurred: {e}")

if __name__ == "__main__":
    try:
        voice_chat()
    except KeyboardInterrupt:
        print("\nStopped by user.")