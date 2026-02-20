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

avi_filename = os.path.join(OUTPUT_DIR, f"debug_recording_{get_timestamp()}.avi")
mp4_filename = avi_filename.replace('.avi', '.mp4')

print(f"Debug Recording")
print(f"==============")
print(f"Stream: {STREAM_URL}")
print(f"AVI output: {avi_filename}")
print(f"MP4 output: {mp4_filename}")
print("")
print("Step 1: Recording raw MJPEG stream to AVI")
print("Press Ctrl+C to stop")
print("")

# Step 1: Record to AVI with copy mode
cmd1 = [
    "ffmpeg",
    "-hide_banner",
    "-loglevel", "info",  # Show info for debugging
    "-thread_queue_size", "8192",
    "-i", STREAM_URL,
    "-c:v", "copy",
    "-f", "avi",
    "-y",
    avi_filename
]

print("Command:", " ".join(cmd1))
print("")

try:
    result1 = subprocess.run(cmd1)
except KeyboardInterrupt:
    print("\n\nStopped by user")

print("")
if not os.path.exists(avi_filename) or os.path.getsize(avi_filename) == 0:
    print("✗ Recording failed - AVI file is empty or missing")
    exit(1)

avi_size = os.path.getsize(avi_filename) / (1024 * 1024)
print(f"✓ AVI recorded: {avi_size:.2f} MB")
print("")

# Step 2: Convert to MP4 with proper timing
print("Step 2: Converting AVI to MP4 with proper timing...")

cmd2 = [
    "ffmpeg",
    "-hide_banner",
    "-loglevel", "info",
    "-i", avi_filename,
    "-c:v", "libx264",
    "-preset", "ultrafast",
    "-crf", "28",
    "-r", "15",  # Force 15fps output
    "-pix_fmt", "yuv420p",
    "-movflags", "+faststart",
    "-y",
    mp4_filename
]

print("Command:", " ".join(cmd2))
print("")

result2 = subprocess.run(cmd2)

if result2.returncode == 0 and os.path.exists(mp4_filename):
    os.remove(avi_filename)  # Remove temporary AVI
    mp4_size = os.path.getsize(mp4_filename) / (1024 * 1024)
    print(f"\n✓ Conversion complete!")
    print(f"  File: {mp4_filename}")
    print(f"  Size: {mp4_size:.2f} MB")
else:
    print(f"\n✗ Conversion failed")
    print(f"  Raw AVI kept: {avi_filename}")
    exit(1)

# Show video info
print("\nVideo Info:")
os.system(f'ffprobe -v error -show_entries stream=r_frame_rate,avg_frame_rate,duration,nb_frames -of default=noprint_wrappers=1 "{mp4_filename}"')
