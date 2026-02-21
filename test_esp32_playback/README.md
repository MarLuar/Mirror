# ESP32 UDP Audio Playback Test

This is a simple test to send a WAV file from your laptop to an ESP32 via UDP and play it through a speaker connected to a MAX98357A I2S amplifier.

## Files

| File | Description |
|------|-------------|
| `test_esp32_playback.ino` | **Main sketch** - ESP32 with I2S audio playback (FIXED version) |
| `test_udp_debug.ino` | **Debug sketch** - UDP test without I2S (use this first if having crashes) |
| `send_wav_to_esp32.py` | Python script to send WAV file via UDP |
| `README.md` | This documentation |

## Hardware Requirements

- ESP32 DevKit
- MAX98357A I2S Amplifier Module
- Speaker (4-8 Ohm)
- WiFi connection (ESP32 connects to "ubuntu" network)

## Wiring

```
MAX98357A    ESP32
---------    -----
VCC    -->   3.3V
GND    -->   GND
BCLK   -->   GPIO 26
LRC    -->   GPIO 27
DIN    -->   GPIO 14
SD     -->   3.3V (or leave floating for always-on)
```

Connect speaker to the MAX98357A output terminals.

## Software Setup

### 1. Upload ESP32 Firmware

**First time? Start with the debug sketch:**

1. Open `test_udp_debug.ino` in Arduino IDE (this tests UDP without I2S)
2. Upload to ESP32 and test with: `python3 -c "import socket; s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.sendto(b'TEST',('10.42.0.156',1235))"`
3. If that works without rebooting, proceed to the main sketch

**Main audio playback sketch:**

1. Open `test_esp32_playback.ino` in Arduino IDE
2. Update WiFi credentials if needed (default: SSID="ubuntu", password="ubuntubuntu")
3. Update `ESP32_IP` in the Python script if your ESP32 has a different IP
4. Upload to ESP32
5. Open Serial Monitor (115200 baud) to see status messages

### 2. Send Audio from Laptop

```bash
cd /home/koogs/Documents/Mirror/speech-analyzer/test_esp32_playback
python3 send_wav_to_esp32.py /home/koogs/Documents/Mirror/speech-analyzer/recordings/esp32_prompted_speech_20260221_193100.wav
```

Or make it executable and run:

```bash
chmod +x send_wav_to_esp32.py
./send_wav_to_esp32.py /home/koogs/Documents/Mirror/speech-analyzer/recordings/esp32_prompted_speech_20260221_193100.wav
```

## How It Works

1. ESP32 connects to WiFi and starts a UDP server on port 1235
2. Python script reads the WAV file and sends it in 1024-byte chunks via UDP
3. ESP32 receives the packets and plays them immediately through I2S
4. After 500ms of no packets, playback ends with a completion beep

## Serial Commands

While the ESP32 is running, you can send commands via Serial Monitor:

- `BEEP` or `TEST` - Play a test beep to verify speaker is working
- `INFO` or `STATUS` - Show current status (WiFi, IP, etc.)

## Debugging Crashes/Reboots

If your ESP32 reboots when receiving UDP packets, try this debug process:

### Step 1: Test UDP Only (No I2S)
Upload `test_udp_debug.ino` first - this receives UDP packets without any I2S code.

```bash
python3 -c "import socket; s=socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.sendto(b'TEST',('10.42.0.156',1235))"
```

If this works without rebooting, the issue is with I2S.
If it still reboots, the issue is with WiFi/UDP configuration.

### Step 2: Check Watchdog Timer
The most common cause of crashes is the watchdog timer. The FIXED version includes:
- `yield()` calls to feed the watchdog
- Timeouts on blocking functions
- Smaller buffers

### Step 3: Check Power Supply
UDP + WiFi + I2S can draw significant current. Make sure:
- USB cable is good quality (not a cheap charging-only cable)
- Power supply can provide 500mA+ 
- Try a different USB port or powered USB hub

## Troubleshooting

1. **ESP32 reboots when receiving UDP:**
   - Use the FIXED version (`test_esp32_playback.ino`)
   - Try `test_udp_debug.ino` first to isolate the issue
   - Check power supply (insufficient power causes reboots)
   - Reduce buffer size further if needed
   - Check Serial Monitor for stack trace (Guru Meditation Error)

2. **No sound from speaker:**
   - Check wiring (BCLK→GPIO26, LRC→GPIO27, DIN→GPIO14)
   - Make sure SD pin on MAX98357A is connected to 3.3V
   - Check Serial Monitor for I2S initialization messages
   - Try the `BEEP` serial command to test speaker

2. **ESP32 not receiving data:**
   - Check ESP32 IP address in Serial Monitor
   - Update `ESP32_IP` in Python script to match
   - Make sure laptop and ESP32 are on the same WiFi network
   - Check firewall settings (UDP port 1235)

3. **Garbled audio:**
   - Make sure WAV file is 16-bit PCM
   - Mono (1 channel) works best
   - Sample rate should be 44100 Hz

4. **Audio too quiet/loud:**
   - Adjust volume on the MAX98357A (gain pin if available)
   - Or modify the audio data amplitude in the ESP32 code

## Notes

- The WAV file header is sent as audio data too (will sound like a short click)
- For best results, use mono 16-bit 44100Hz WAV files
- UDP is lossy - some packets may be dropped causing minor audio glitches
