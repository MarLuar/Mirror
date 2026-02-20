#!/usr/bin/env python3
"""
ESP32-CAM Trigger-based Recording Script

This script monitors the ESP32-CAM's recording status and automatically
starts/stops ffmpeg recording based on the trigger state.

Usage:
    python3 record_triggered.py

Requirements:
    - ffmpeg installed and in PATH
    - requests library: pip install requests
"""

import requests
import subprocess
import time
import signal
import sys
import os
import select
from datetime import datetime

# Configuration
# ESP32-CAM IP Address (from Serial Monitor)
ESP32_IP = "10.42.0.82"
STREAM_URL = f"http://{ESP32_IP}:81/stream"
STATUS_URL = f"http://{ESP32_IP}/status"
CONTROL_URL = f"http://{ESP32_IP}/control"
OUTPUT_DIR = "recordings"
CHECK_INTERVAL = 0.5  # seconds

# State
recording = False
ffmpeg_process = None
connection_ok = False
error_count = 0
MAX_ERRORS_BEFORE_PRINT = 5


def ensure_output_dir():
    """Create output directory if it doesn't exist."""
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"Created output directory: {OUTPUT_DIR}")


def get_timestamp():
    """Get current timestamp string."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def start_recording():
    """Start ffmpeg recording process."""
    global ffmpeg_process
    ensure_output_dir()
    
    filename = os.path.join(OUTPUT_DIR, f"recording_{get_timestamp()}.mp4")
    print(f"\n{'='*50}")
    print(f"[RECORDING STARTED]")
    print(f"Output file: {filename}")
    print(f"{'='*50}\n")
    
    try:
        ffmpeg_process = subprocess.Popen(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel", "error",
                "-f", "mjpeg",          # Force MJPEG format
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
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return True
    except FileNotFoundError:
        print("ERROR: ffmpeg not found! Please install ffmpeg.")
        print("  Ubuntu/Debian: sudo apt-get install ffmpeg")
        print("  macOS: brew install ffmpeg")
        print("  Windows: https://ffmpeg.org/download.html")
        return False


def stop_recording():
    """Stop ffmpeg recording process gracefully."""
    global ffmpeg_process
    if ffmpeg_process:
        print(f"\n{'='*50}")
        print("[RECORDING STOPPED]")
        print("Finalizing video file...")
        
        # Send SIGTERM for graceful shutdown
        ffmpeg_process.terminate()
        
        # Wait for ffmpeg to finish (max 5 seconds)
        try:
            ffmpeg_process.wait(timeout=5)
            print("Video saved successfully!")
        except subprocess.TimeoutExpired:
            print("Force stopping ffmpeg...")
            ffmpeg_process.kill()
            ffmpeg_process.wait()
        
        ffmpeg_process = None
        print(f"{'='*50}\n")


def check_recording_status():
    """Check if recording is requested from ESP32-CAM."""
    global connection_ok, error_count
    
    try:
        response = requests.get(STATUS_URL, timeout=2)
        data = response.json()
        
        # Connection successful
        if not connection_ok:
            print(f"[CONNECTED] ESP32-CAM at {ESP32_IP}")
            connection_ok = True
            error_count = 0
        
        return data.get("recording_requested", False)
        
    except requests.exceptions.ConnectionError:
        if connection_ok:
            print(f"[DISCONNECTED] Cannot connect to ESP32-CAM at {ESP32_IP}")
            connection_ok = False
        error_count += 1
        if error_count % MAX_ERRORS_BEFORE_PRINT == 1:
            print(f"[RETRYING] Trying to reconnect... ({error_count})")
        return None
        
    except requests.exceptions.Timeout:
        if error_count % MAX_ERRORS_BEFORE_PRINT == 1:
            print("[WARNING] Request timeout - ESP32-CAM may be busy.")
        error_count += 1
        return None
        
    except Exception as e:
        if error_count % MAX_ERRORS_BEFORE_PRINT == 1:
            print(f"[ERROR] {type(e).__name__}: {e}")
        error_count += 1
        return None


def trigger_record():
    """Send HTTP trigger to start recording."""
    try:
        requests.get(f"{CONTROL_URL}?cmd=record", timeout=2)
        print("[SENT] Record command via HTTP")
    except Exception as e:
        print(f"[ERROR] Failed to send record command: {e}")


def trigger_stop():
    """Send HTTP trigger to stop recording."""
    try:
        requests.get(f"{CONTROL_URL}?cmd=stop", timeout=2)
        print("[SENT] Stop command via HTTP")
    except Exception as e:
        print(f"[ERROR] Failed to send stop command: {e}")


def print_status_header():
    """Print script information."""
    print("="*60)
    print("ESP32-CAM Trigger-based Recording Script")
    print("="*60)
    print(f"ESP32-CAM IP: {ESP32_IP}")
    print(f"Stream URL: {STREAM_URL}")
    print(f"Output Directory: {OUTPUT_DIR}")
    print("-"*60)
    print("Commands:")
    print("  r/record  - Manually trigger recording via HTTP")
    print("  s/stop    - Manually stop recording via HTTP")
    print("  q/quit    - Exit script")
    print("="*60)
    print("")


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully."""
    print("\n\nShutting down...")
    stop_recording()
    sys.exit(0)


def main():
    global recording
    
    # Register signal handler for clean exit
    signal.signal(signal.SIGINT, signal_handler)
    
    print_status_header()
    
    # Wait for initial connection
    print("Connecting to ESP32-CAM...")
    retry_count = 0
    while True:
        status = check_recording_status()
        if status is not None:
            print("\n✓ Connected! Waiting for recording trigger...")
            print("(You can also trigger via ESP-NOW device or Serial)")
            print("")
            break
        
        retry_count += 1
        if retry_count >= 10:
            print("\n⚠️  Could not connect to ESP32-CAM after 10 attempts.")
            print("   Starting anyway - will retry automatically...")
            print("")
            break
        
        time.sleep(1)
    
    # Main loop
    while True:
        # Check for manual commands from stdin
        if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
            cmd = sys.stdin.readline().strip().lower()
            if cmd in ['r', 'record', 'start']:
                trigger_record()
            elif cmd in ['s', 'stop', 'end']:
                trigger_stop()
            elif cmd in ['q', 'quit', 'exit']:
                signal_handler(None, None)
        
        # Check ESP32-CAM recording status
        is_recording_requested = check_recording_status()
        
        if is_recording_requested is not None:
            if is_recording_requested and not recording:
                if start_recording():
                    recording = True
            elif not is_recording_requested and recording:
                stop_recording()
                recording = False
        
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
