# Option 3: Audio Playback via CAM SD + ESP-NOW

This feature allows the laptop to send audio to the ESP32-CAM, store it on the CAM's SD card, then have the CAM stream the audio via ESP-NOW to the main ESP32 for playback.

## How It Works

1. **Laptop** sends audio file to **CAM** via HTTP POST (`/audio_upload`)
2. **CAM** stores audio on SD card
3. **Laptop** sends play command to CAM (`/audio_play`)
4. **CAM** reads audio from SD and streams chunks via ESP-NOW to main ESP32
5. **Main ESP32** receives chunks, buffers them, then plays audio smoothly

## Setup Instructions

### Step 1: Get Main ESP32 MAC Address

Upload this sketch to your main ESP32 (the one with the button and OLED) to get its MAC address:

```cpp
#include <WiFi.h>
void setup() {
  Serial.begin(115200);
  WiFi.begin("dummy", "dummy");  // Just to initialize WiFi
  delay(1000);
  Serial.println();
  Serial.print("Main ESP32 MAC: ");
  Serial.println(WiFi.macAddress());
}
void loop() {}
```

Note down the MAC address (format: `AA:BB:CC:DD:EE:FF`).

### Step 2: Update Camera Firmware

Open `esp32_cam_wifi/esp32cam_stream/camera_firmware/camera_firmware.ino` and update line 72:

```cpp
// REPLACE THIS:
uint8_t mainESP32MAC[] = {0xXX, 0xXX, 0xXX, 0xXX, 0xXX, 0xXX};

// WITH YOUR MAIN ESP32 MAC (example):
uint8_t mainESP32MAC[] = {0xA0, 0xB7, 0x65, 0xXX, 0xXX, 0xXX};
```

Convert your MAC address from `AA:BB:CC:DD:EE:FF` format to `{0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF}`.

### Step 3: Upload Firmware

1. **Camera Firmware**: Upload `camera_firmware.ino` to ESP32-CAM
2. **Main Firmware**: Upload `main_firmware_button_toggle.ino` to main ESP32

### Step 4: Update Python Script

The `button_trigger_analyzer.py` already has the new methods. No changes needed.

## Usage

### Method 1: Using New Methods (Option 3)

In your Python script or interactively:

```python
# After recording and analysis

# 1. Send audio to CAM SD card
analyzer.send_audio_to_cam("recordings/raw/button_trigger_XXXXX.wav", "my_audio.wav")

# 2. Trigger playback from CAM via ESP-NOW
analyzer.play_audio_from_cam()
```

### Method 2: Modify Existing Workflow

Replace the existing `send_playback` call in `process_recording`:

```python
# OLD (direct UDP playback):
# self.send_playback(wav_path)

# NEW (Option 3 - via CAM):
self.send_audio_to_cam(wav_path, "playback.wav")
time.sleep(1)  # Wait for upload
self.play_audio_from_cam()
```

## API Endpoints (CAM)

### POST `/audio_upload?file=<filename>`
Upload audio file to CAM's SD card.

**Example:**
```bash
curl -X POST -H "Content-Type: application/octet-stream" \
     --data-binary @audio.wav \
     "http://10.42.0.82/audio_upload?file=playback.wav"
```

### GET `/audio_play`
Trigger CAM to stream audio via ESP-NOW to main ESP32.

**Example:**
```bash
curl "http://10.42.0.82/audio_play"
```

## Files Changed

1. **`camera_firmware.ino`** - Added:
   - `mainESP32MAC[]` - Update with your main ESP32 MAC
   - `audio_upload_handler` - HTTP endpoint to receive audio
   - `audio_play_handler` - HTTP endpoint to trigger playback
   - `streamAudioViaESPNow()` - Streams audio chunks via ESP-NOW

2. **`main_firmware_button_toggle.ino`** - Added:
   - `audio_chunk_msg` structure for ESP-NOW packets
   - `OnDataRecv()` callback to receive audio chunks
   - `playESPNowAudio()` to play buffered audio
   - 32KB audio buffer

3. **`button_trigger_analyzer.py`** - Added:
   - `send_audio_to_cam(wav_path, filename)` - Upload audio to CAM
   - `play_audio_from_cam()` - Trigger ESP-NOW playback

## Existing Features

All existing features remain unchanged:
- Button recording trigger
- ESP-NOW camera trigger
- OLED display
- Speech analysis
- Video download
- Direct UDP playback (original method still works)

## Troubleshooting

### "ESP-NOW peer not configured"
- Make sure you updated `mainESP32MAC` in camera firmware
- Check that both ESP32s are on the same WiFi channel

### Audio not playing
- Check serial monitor on both ESP32s
- Verify SD card is working on CAM
- Ensure CAM has enough free space on SD

### Choppy audio
- This is ESP-NOW limitation - try shorter audio clips
- Increase `delay(5)` in `streamAudioViaESPNow()` if needed
