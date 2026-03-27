import socket

# --- API Configuration ---
OPENAI_API_KEY = ""

# --- Networking ---
ROBOT_UDP_IP = "127.0.0.1"
ROBOT_UDP_PORT = 5005
TTS_UDP_PORT = 5006

# --- Game Logic ---
MIMIC_PROMPT = {
    "id": "pmpt_69b5a72f3b8c819491ad004531919a9b05f7f92fd2ab1d24",
    "version": "2"
}

GRID_MAPPING = """
Here are the valid board positions (0-8) and their physical locations:
0: bottom left | 1: bottom middle | 2: bottom right
3: middle left | 4: center        | 5: middle right
6: top left    | 7: top middle    | 8: top right
"""