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
# Uses ultrafast preset and zerolatency tune for minimal delay
# Fixed 15fps output to prevent fast-forward/slow-motion issues
cmd = [
    "ffmpeg",
    "-hide_banner",
    "-loglevel", "info",  # Show info for debugging
    "-fflags", "+discardcorrupt",
    "-reconnect", "1",
    "-reconnect_streamed", "1",
    "-reconnect_delay_max", "5",
    "-thread_queue_size", "4096",
    "-i", STREAM_URL,
    "-c:v", "libx264",
    "-preset", "ultrafast",  # Fastest encoding to prevent packet loss
    "-tune", "zerolatency",  # Optimize for low latency
    "-crf", "28",            # Balance between quality and speed
    "-r", "15",              # Force 15fps output (prevents fast-forward)
    "-pix_fmt", "yuv420p",   # Standard pixel format
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

# Check file size
if os.path.exists(filename):
    size = os.path.getsize(filename)
    if size == 0:
        print("\n⚠️ WARNING: File is empty!")
    else:
        print(f"\n✓ File size: {size / (1024*1024):.2f} MB")
