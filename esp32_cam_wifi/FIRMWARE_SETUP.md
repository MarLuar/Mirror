# ESP32 Camera + Audio Integration Setup

This setup integrates the **main_firmware** (audio ESP32) with **camera_firmware** (camera ESP32) using ESP-NOW for wireless camera triggering.

## Architecture

```
┌──────────────────┐      ESP-NOW       ┌──────────────────┐
│  main_firmware   │  ─────────────────>│ camera_firmware  │
│  (Audio + TX)    │    Record/Stop     │  (Camera + RX)   │
│  DHCP (Audio)    │                    │  DHCP (Camera)   │
└──────────────────┘                    └──────────────────┘
         │                                        │
         │ UDP Audio                              │ HTTP Stream
         v                                        v
   ┌──────────┐                             ┌──────────┐
   │  Laptop  │                             │  Laptop  │
   │  (Server)│                             │ (ffmpeg) │
   └──────────┘                             └──────────┘
```

## Setup Instructions

### Step 1: Upload camera_firmware

1. Open `esp32cam_stream/camera_firmware/camera_firmware.ino` in Arduino IDE
2. Select board: **ESP32 Wrover Module**
3. Upload to your ESP32-CAM
4. Open Serial Monitor (115200 baud) and note the **MAC Address**
   
   Example output:
   ```
   MAC Address: A4:CF:12:34:56:78
   IMPORTANT: Use this MAC for main_firmware:
   A4:CF:12:34:56:78
   ```

### Step 2: Update main_firmware with Camera MAC

1. Open `main_firmware/main_firmware.ino`
2. Find line ~31 and replace the MAC address:
   ```cpp
   // REPLACE WITH YOUR CAMERA'S ACTUAL MAC
   uint8_t cameraMAC[] = {0xA4, 0xCF, 0x12, 0x34, 0x56, 0x78};
   ```
3. Upload to your audio ESP32

### Step 3: Trigger Recording

You can trigger camera recording in 3 ways:

#### 1. Serial Command (Serial Monitor)
```
RECORD    - Start camera recording
STOP      - Stop camera recording
```

#### 2. Button Press (GPIO 0 - Boot Button)
- Press the boot button to toggle recording on/off

#### 3. Dynamic MAC Setup (if you change cameras)
```
CAMMAC A4:CF:12:34:56:78    - Set camera MAC address
```

## Network Configuration

| Device | IP Address | Port | Protocol |
|--------|-----------|------|----------|
| main_firmware (Audio) | DHCP Assigned | 1234/1235 | UDP |
| camera_firmware (Video) | DHCP Assigned | 80/81 | HTTP |
| Laptop | DHCP Assigned | - | UDP/HTTP |

> **Note:** All devices use DHCP. Check Serial Monitor on each ESP32 to see their assigned IP addresses.

## Recording Workflow

1. Start both ESP32 devices
2. Verify connection (check Serial Monitor for "ESP-NOW Send Status: Success")
3. Trigger recording using:
   - Serial command `RECORD`
   - Boot button press
4. Camera will start recording indication
5. Use ffmpeg scripts on PC to capture the stream:
   ```bash
   ./record.sh record
   ```
6. Stop with `STOP` command or button press

## Troubleshooting

### "Failed to add camera as peer!"
- Make sure you've set the correct MAC address
- Check Serial Monitor on camera for its MAC

### "ESP-NOW Send Status: Fail"
- Both ESP32s must be on the same WiFi channel
- Restart both devices
- Check WiFi connection on both

### Camera not responding
- Verify camera stream works: `http://<CAMERA_IP>:81/stream` (check Serial Monitor for IP)
- Check camera Serial Monitor for ESP-NOW messages
- Try setting MAC again with `CAMMAC` command

## Files

| File | Description |
|------|-------------|
| `main_firmware/main_firmware.ino` | Audio ESP32 with ESP-NOW transmitter |
| `esp32cam_stream/camera_firmware/camera_firmware.ino` | Camera ESP32 with ESP-NOW receiver |
| `record.sh` | Linux/macOS recording script |
| `record.bat` | Windows recording script |
| `record_triggered.py` | Python trigger-based recorder |
