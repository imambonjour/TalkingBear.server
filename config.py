import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DEVICE_SECRET_KEY = os.getenv("DEVICE_SECRET_KEY")

# Audio settings (harus sama dengan konfigurasi ESP32)
SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2  # 16-bit = 2 bytes
