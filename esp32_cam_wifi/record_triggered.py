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
CHECK_INTERVAL = 1.0  # seconds - increased to prevent rapid toggling

# State
recording = False
ffmpeg_process = None
connection_ok = False
error_count = 0
MAX_ERRORS_BEFORE_PRINT = 5
recording_start_time = None
MIN_RECORDING_DURATION = 3.0  # Minimum seconds before allowing stop (prevents rapid toggling)


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
    global ffmpeg_process, recording_start_time
    ensure_output_dir()
    recording_start_time = time.time()  # Track when recording started
    
    filename = os.path.join(OUTPUT_DIR, f"recording_{get_timestamp()}.mp4")
    print(f"\n{'='*50}")
    print(f"[RECORDING STARTED]")
    print(f"Output file: {filename}")
    print(f"Stream URL: {STREAM_URL}")
    print(f"{'='*50}\n")
    
    # First, test if stream is accessible
    print("Testing stream accessibility...")
    try:
        import urllib.request
        # Use GET with a small range to test (HEAD might not be supported)
        req = urllib.request.Request(STREAM_URL)
        req.add_header('Range', 'bytes=0-1024')
        with urllib.request.urlopen(req, timeout=5) as response:
            content_type = response.headers.get('Content-Type', 'unknown')
            print(f"  ✓ Stream is accessible (Status: {response.status}, Content-Type: {content_type})")
    except Exception as e:
        print(f"  ⚠ Stream test warning: {e}")
        print("  Continuing anyway...")
    
    try:
        # Create a log file for ffmpeg errors
        log_file = os.path.join(OUTPUT_DIR, f"ffmpeg_{get_timestamp()}.log")
        
        # Try simple copy mode first for testing, then fall back to re-encoding if needed
        # The stream from ESP32-CAM is already MJPEG, we can copy it directly
        # But for compatibility we'll use libx264 with proper settings
        
        ffmpeg_process = subprocess.Popen(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel", "info",    # Show info for debugging (change to warning later)
                "-rw_timeout", "5000000",  # 5 second read timeout for network
                "-reconnect", "1",
                "-reconnect_streamed", "1",
                "-reconnect_delay_max", "5",
                "-thread_queue_size", "4096",  # Larger input buffer for network streams
                "-i", STREAM_URL,
                "-c:v", "copy",         # First try copying the stream directly (no re-encoding)
                "-movflags", "+faststart+frag_keyframe",
                "-y",
                filename
            ],
            stdout=subprocess.DEVNULL,
            stderr=open(log_file, 'w')  # Log errors to file instead of hiding
        )
        print(f"  ffmpeg PID: {ffmpeg_process.pid}")
        print(f"  ffmpeg log: {log_file}")
        print(f"  Mode: copy (no re-encoding)")
        return True
    except FileNotFoundError:
        print("ERROR: ffmpeg not found! Please install ffmpeg.")
        print("  Ubuntu/Debian: sudo apt-get install ffmpeg")
        print("  macOS: brew install ffmpeg")
        print("  Windows: https://ffmpeg.org/download.html")
        return False
    except Exception as e:
        print(f"ERROR starting ffmpeg: {e}")
        return False


def stop_recording():
    """Stop ffmpeg recording process gracefully."""
    global ffmpeg_process
    if ffmpeg_process:
        print(f"\n{'='*50}")
        print("[RECORDING STOPPED]")
        print("Finalizing video file...")
        
        # Get the return code if process already exited
        return_code = ffmpeg_process.poll()
        
        if return_code is None:
            # Process is still running, send SIGTERM for graceful shutdown
            print("  Stopping ffmpeg gracefully...")
            ffmpeg_process.terminate()
            
            # Wait for ffmpeg to finish (max 10 seconds)
            try:
                return_code = ffmpeg_process.wait(timeout=10)
                if return_code == 0:
                    print("  ✓ ffmpeg stopped successfully")
                else:
                    print(f"  ⚠ ffmpeg exited with code: {return_code}")
            except subprocess.TimeoutExpired:
                print("  ⚠ ffmpeg didn't stop in time, force killing...")
                ffmpeg_process.kill()
                ffmpeg_process.wait()
        else:
            print(f"  ⚠ ffmpeg already exited with code: {return_code}")
        
        ffmpeg_process = None
        
        # Check if video file was created and has content
        import glob
        latest_files = sorted(glob.glob(os.path.join(OUTPUT_DIR, "recording_*.mp4")), 
                             key=os.path.getmtime, reverse=True)
        if latest_files:
            latest_file = latest_files[0]
            size = os.path.getsize(latest_file)
            if size == 0:
                print(f"  ✗ WARNING: Video file is empty ({size} bytes)")
                print("  Check ffmpeg log file for errors")
            else:
                size_mb = size / (1024 * 1024)
                print(f"  ✓ Video saved: {os.path.basename(latest_file)} ({size_mb:.2f} MB)")
        
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
                # Start recording
                if start_recording():
                    recording = True
            elif not is_recording_requested and recording:
                # Check minimum recording duration before stopping
                elapsed = time.time() - recording_start_time if recording_start_time else 0
                if elapsed >= MIN_RECORDING_DURATION:
                    stop_recording()
                    recording = False
                else:
                    # Too soon to stop, ignore the stop request
                    if int(elapsed) % 1 == 0:  # Print every second
                        print(f"  [Recording for {elapsed:.1f}s, minimum {MIN_RECORDING_DURATION}s]")
        
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
