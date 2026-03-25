import socket

# --- API Configuration ---


# --- Networking ---
ROBOT_UDP_IP = "127.0.0.1"
ROBOT_UDP_PORT = 5005
TTS_UDP_PORT = 5006

# --- Game Logic ---
MIMIC_PROMPT = {
    "id": "pmpt_69b5a72f3b8c819491ad004531919a9b05f7f92fd2ab1d24",
    "version": "1"
}

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