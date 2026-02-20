# ESP32-CAM MJPEG Stream Server with Recording Triggers

ESP32-CAM (AI Thinker) streaming server with ESP-NOW and Serial trigger support for recording control.

## Network Configuration

| Setting | Value |
|---------|-------|
| SSID | `ubuntu` |
| Password | `ubuntubuntu` |
| IP Assignment | DHCP (Automatic) |
| Expected IP Range | `10.42.0.x` (confirmed from main_firmware)

> **Note:** With DHCP, the ESP32-CAM will automatically receive an IP address from your hotspot. Check the Serial Monitor after boot to see the assigned IP address.

## Project Structure

```
esp32cam_stream/
├── esp32cam_stream.ino          # Main ESP32-CAM code
└── espnow_transmitter/
    └── espnow_transmitter.ino   # ESP-NOW remote control
```

## Hardware Requirements

### ESP32-CAM (Main Device)
- AI Thinker ESP32-CAM module
- FTDI/USB-to-TTL programmer (for initial upload)
- Power supply (5V)

### ESP32 Remote (Optional - for wireless trigger)
- Any ESP32 dev board
- Push button (connected between GPIO 4 and GND)

### Connection Diagram for Programming
```
FTDI/Programmer    ESP32-CAM
-----------        ---------
GND      --------> GND
5V       --------> 5V
TX       --------> U0R (GPIO3)
RX       --------> U0T (GPIO1)
GND      --------> GPIO0  (for programming mode)
```
**Note:** Connect GPIO0 to GND before powering on to enter programming mode.

## Setup Instructions

### 1. ESP32-CAM Setup

1. Open `esp32cam_stream/esp32cam_stream.ino` in Arduino IDE
2. Select Board: `ESP32 Wrover Module`
3. Select Partition Scheme: `Huge APP (3MB No OTA/1MB SPIFFS)`
4. Upload the code
5. Open Serial Monitor at 115200 baud
6. Note the MAC address displayed (needed for ESP-NOW transmitter)

### 2. ESP-NOW Transmitter Setup (Optional)

1. Open `esp32cam_stream/espnow_transmitter/espnow_transmitter.ino`
2. Update the MAC address in the code:
   ```cpp
   uint8_t esp32CamAddress[] = {0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF}; // Your ESP32-CAM MAC
   ```
3. Upload to your second ESP32 device
4. Connect a button between GPIO 4 and GND

## Access Points

Once connected, the ESP32-CAM provides:

| Endpoint | URL | Description |
|----------|-----|-------------|
| Web Interface | `http://<ESP32_IP>` | Browser-based control panel (check Serial for IP) |
| MJPEG Stream | `http://<ESP32_IP>:81/stream` | Video stream for ffmpeg |
| Status API | `http://<ESP32_IP>/status` | JSON status info |
| Control API | `http://<ESP32_IP>/control?cmd=record` | HTTP trigger commands |

> **Finding the IP:** After connecting, the ESP32 will print its IP in the Serial Monitor. Update `record_triggered.py` with this IP.

## Recording Triggers

### Method 1: Serial Commands (USB/Serial)
Connect to ESP32-CAM via Serial Monitor and send:
```
RECORD    # or REC, START - Start recording indication
STOP      # or END - Stop recording indication
STATUS    # Show current status
HELP      # Show available commands
```

### Method 2: ESP-NOW (Wireless)
Use the ESP-NOW transmitter:
- **Button**: Press to toggle record/stop
- **Serial**: Send `r`, `record`, or `start` to begin; `s`, `stop`, or `end` to stop

### Method 3: HTTP API
```bash
# Start recording
curl "http://<ESP32_IP>/control?cmd=record"  # Replace <ESP32_IP> with actual IP from Serial Monitor

# Stop recording
curl "http://<ESP32_IP>/control?cmd=stop"  # Replace <ESP32_IP> with actual IP from Serial Monitor

# Check status
curl "http://<ESP32_IP>/status"  # Replace <ESP32_IP> with actual IP from Serial Monitor
```

### Method 4: Web Interface
Open `http://<ESP32_IP>` in a browser (replace with actual IP from Serial Monitor) and use the on-screen buttons.

## FFmpeg Recording Commands

### Basic Recording (Auto-detect when recording header is present)
```bash
# Simple recording - saves when X-Recording header is 1
ffmpeg -i "http://<ESP32_IP>:81/stream" -c copy output.mp4  # Replace <ESP32_IP> with actual IP
```

### Continuous Recording with Timestamp
```bash
ffmpeg -i "http://<ESP32_IP>:81/stream" \
  -c copy -f segment -segment_time 300 \
  -reset_timestamps 1 -strftime 1 \
  "recording_%Y%m%d_%H%M%S.mp4"  # Replace <ESP32_IP> with actual IP
```

### Record with Reconnection (robust)
```bash
ffmpeg -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 \
  -i "http://<ESP32_IP>:81/stream" \
  -c copy -f segment -segment_time 60 \
  "segment_%03d.mp4"  # Replace <ESP32_IP> with actual IP
```

### View Live Stream (no recording)
```bash
ffplay "http://<ESP32_IP>:81/stream"  # Replace <ESP32_IP> with actual IP
```

### Record with Date-based Filename
```bash
ffmpeg -i "http://<ESP32_IP>:81/stream" \
  -c copy "recording_$(date +%Y%m%d_%H%M%S).mp4"  # Replace <ESP32_IP> with actual IP
```

### Python Script for Trigger-based Recording
Save as `record_triggered.py`:
```python
import requests
import subprocess
import time
import signal
import sys

ESP32_IP = "192.168.100.91"  # UPDATE THIS: Check Serial Monitor for actual IP
STREAM_URL = f"http://{ESP32_IP}:81/stream"
recording = False
ffmpeg_process = None

def start_recording():
    global ffmpeg_process
    filename = time.strftime("recording_%Y%m%d_%H%M%S.mp4")
    print(f"Starting recording: {filename}")
    ffmpeg_process = subprocess.Popen([
        "ffmpeg", "-i", STREAM_URL, 
        "-c", "copy", "-y", filename
    ])

def stop_recording():
    global ffmpeg_process
    if ffmpeg_process:
        print("Stopping recording...")
        ffmpeg_process.terminate()
        ffmpeg_process.wait()
        ffmpeg_process = None

def check_status():
    try:
        r = requests.get(f"http://{ESP32_IP}/status", timeout=2)
        return r.json().get("recording_requested", False)
    except:
        return False

def signal_handler(sig, frame):
    stop_recording()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

print("Waiting for recording trigger...")
while True:
    is_recording = check_status()
    
    if is_recording and not recording:
        start_recording()
        recording = True
    elif not is_recording and recording:
        stop_recording()
        recording = False
    
    time.sleep(0.5)
```

Run with:
```bash
python3 record_triggered.py
```

## PlatformIO Setup (Alternative)

If using PlatformIO, create `platformio.ini`:

```ini
[env:esp32cam]
platform = espressif32
board = esp32cam
framework = arduino
monitor_speed = 115200
board_build.partitions = huge_app.csv
build_flags = 
    -DBOARD_HAS_PSRAM
    -mfix-esp32-psram-cache-issue
```

## Troubleshooting

### Camera Init Failed
- Check wiring and power supply (use external 5V supply, not USB power)
- Ensure GPIO0 is NOT connected to GND after programming
- Try resetting the board

### WiFi Connection Issues
- Verify SSID and password in code
- Check if static IP is not already in use
- Ensure WiFi router supports the ESP32

### ESP-NOW Not Working
- Ensure both devices are on the same WiFi channel
- Verify MAC address is correct in transmitter code
- Check Serial Monitor for "Delivery Success" messages

### Poor Video Quality
- Adjust `config.jpeg_quality` (lower = better quality, higher CPU usage)
- Change `config.frame_size` (e.g., `FRAMESIZE_HD` for 1280x720)
- Ensure good WiFi signal strength

### Stream Lag/Stuttering
- Reduce resolution: `config.frame_size = FRAMESIZE_CIF` (400x296)
- Lower frame rate in ffmpeg: `-r 15`
- Use wired connection between laptop and router if possible

## License

MIT License - Free to use and modify.
