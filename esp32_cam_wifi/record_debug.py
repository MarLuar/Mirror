#!/usr/bin/env python3
"""Debug version with verbose ffmpeg output"""

import subprocess
import os
from datetime import datetime

# ESP32-CAM IP Address (from Serial Monitor)
ESP32_IP = "10.42.0.82"
STREAM_URL = f"http://{ESP32_IP}:81/stream"
OUTPUT_DIR = "recordings"

def get_timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")

os.makedirs(OUTPUT_DIR, exist_ok=True)
filename = os.path.join(OUTPUT_DIR, f"debug_recording_{get_timestamp()}.mp4")

print(f"Recording to: {filename}")
print("Press Ctrl+C to stop")
print("")

# Debug version - shows ffmpeg output
cmd = [
    "ffmpeg",
    "-f", "mjpeg",
    "-reconnect", "1",
    "-reconnect_streamed", "1",
    "-reconnect_delay_max", "5",
    "-thread_queue_size", "512",  # Increase input buffer
    "-i", STREAM_URL,
    "-c:v", "libx264",
    "-preset", "superfast",
    "-crf", "23",          # Slightly higher CRF for smoother playback
    "-r", "15",             # Force output to 15fps
    "-vf", "fps=15,format=yuv420p",  # Video filter: normalize fps and pixel format
    "-vsync", "cfr",        # Constant frame rate - prevents fast/slow motion
    "-max_muxing_queue_size", "1024",  # Increase muxing buffer
    "-movflags", "+faststart",
    "-y",
    filename
]

print("Command:", " ".join(cmd))
print("")

try:
    subprocess.run(cmd)
except KeyboardInterrupt:
    print("\n\nStopped by user")
    
print(f"\n\nFile saved: {filename}")

# Show video info
print("\nVideo info:")
os.system(f"ffprobe -v error -show_entries stream=avg_frame_rate,r_frame_rate,duration -of default=noprint_wrappers=1 {filename}")
