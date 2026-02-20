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
print(f"Stream: {STREAM_URL}")
print("Press Ctrl+C to stop")
print("")

# Use wallclock timestamps to fix timing issues
cmd = [
    "ffmpeg",
    "-hide_banner",
    "-loglevel", "info",
    "-fflags", "+discardcorrupt+nobuffer",
    "-flags", "+low_delay",
    "-use_wallclock_as_timestamps", "1",  # KEY: Use arrival time
    "-thread_queue_size", "4096",
    "-i", STREAM_URL,
    "-c:v", "libx264",
    "-preset", "ultrafast",
    "-tune", "zerolatency",
    "-crf", "28",
    "-r", "15",
    "-pix_fmt", "yuv420p",
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
if os.path.exists(filename) and os.path.getsize(filename) > 0:
    print("\nVideo info:")
    os.system(f"ffprobe -v error -show_entries stream=r_frame_rate,avg_frame_rate,duration,nb_frames -of default=noprint_wrappers=1 {filename}")
    size_mb = os.path.getsize(filename) / (1024 * 1024)
    print(f"\nFile size: {size_mb:.2f} MB")
else:
    print("\n⚠️ File is empty or doesn't exist")
