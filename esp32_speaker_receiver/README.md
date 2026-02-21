# ESP32 Speaker Receiver

Stream audio from your computer to ESP32 and play it through a MAX98357A amplifier.

## Hardware Requirements

- ESP32 DevKit
- MAX98357A I2S Amplifier Module
- Speaker (4-8Ω)
- WiFi network ("ubuntu" hotspot)

## Wiring

| MAX98357A | ESP32 GPIO | Wire Color |
|-----------|------------|------------|
| VCC       | 3.3V       | Red        |
| GND       | GND        | Black      |
| BCLK      | GPIO 27    | White      |
| LRC (WS)  | GPIO 26    | Green      |
| DIN       | GPIO 14    | Yellow     |
| SD        | 3.3V       | (Enable)   |

**Notes:**
- SD pin high = amplifier enabled (connect to 3.3V)
- SD pin low = shutdown mode
- You can also connect SD to a GPIO for software control

## Setup

### 1. Upload ESP32 Firmware

1. Open `esp32_speaker_receiver.ino` in Arduino IDE
2. Select your ESP32 board and COM port
3. Upload the sketch
4. Open Serial Monitor (115200 baud)
5. Note the IP address shown after WiFi connection

### 2. Update Python Script

Edit `stream_audio_to_esp32.py` and update the ESP32 IP:

```python
ESP32_IP = "10.42.0.156"  # Change to your ESP32's actual IP
```

### 3. Run the Streamer

```bash
cd /home/koogs/Documents/Mirror/speech-analyzer/esp32_speaker_receiver

# Stream a specific file
python stream_audio_to_esp32.py /home/koogs/Documents/Mirror/speech-analyzer/recordings/esp32_prompted_speech_20260221_191358.wav

# Or just run the script to see available recordings
python stream_audio_to_esp32.py
```

## Serial Commands

While the ESP32 is running, you can send commands via Serial Monitor:

| Command | Description |
|---------|-------------|
| `BEEP`  | Play test beep |
| `INFO`  | Show status info |

## How It Works

1. The WAV file is read and sent via UDP in chunks
2. ESP32 receives the stereo audio data
3. Stereo is converted to mono (average of L+R)
4. Audio is played through I2S to the MAX98357A amplifier
5. Playback automatically stops when no packets received for 500ms

## Troubleshooting

### No sound
- Check wiring (BCLK→26, LRC→27, DIN→14)
- Verify SD pin is connected to 3.3V
- Check Serial Monitor for errors
- Ensure ESP32 IP is correct in Python script

### Distorted audio
- Check that your WAV is 16-bit PCM (mono or stereo)
- Reduce the chunk delay in Python script if audio is too slow

### WiFi connection fails
- Check WiFi credentials in the Arduino sketch
- Ensure ESP32 is in range of the WiFi network

## Files

- `esp32_speaker_receiver.ino` - ESP32 firmware
- `stream_audio_to_esp32.py` - Python audio streamer
- `README.md` - This file
