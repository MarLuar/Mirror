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

# Debug version - uses fps filter + setpts to fix fast-forward issue
cmd = [
    "ffmpeg",
    "-hide_banner",
    "-loglevel", "info",
    "-fflags", "+discardcorrupt+igndts",
    "-flags", "+low_delay",
    "-reconnect", "1",
    "-reconnect_streamed", "1",
    "-reconnect_delay_max", "5",
    "-thread_queue_size", "4096",
    "-i", STREAM_URL,
    # Key fix: fps filter normalizes frame rate, setpts fixes timestamps
    "-vf", "fps=fps=15:round=near,setpts=N/FRAME_RATE/TB",
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
    os.system(f"ffprobe -v error -show_entries stream=r_frame_rate,avg_frame_rate,duration -of default=noprint_wrappers=1 {filename}")
    
    # Check duration vs file creation time
    import time
    duration_sec = os.path.getsize(filename) / (100 * 1024)  # Rough estimate: ~100KB per second
    print(f"\nEstimated duration: ~{duration_sec:.1f} seconds")
else:
    print("\n⚠️ File is empty or doesn't exist")
