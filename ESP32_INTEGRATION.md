# ESP32 Speech Analyzer Integration

This project allows you to use an ESP32 with an INMP441 I2S microphone to capture audio and send it to your laptop for speech analysis.

## Components

1. **ESP32 Firmware**: Captures audio from INMP441 microphone and sends it over WiFi
2. **Laptop Server**: Receives audio data and processes it with the speech analyzer
3. **Speech Analyzer**: Analyzes the audio and provides feedback

## Setup Instructions

### 1. Laptop Setup

1. Make sure you have the speech analyzer dependencies installed:
   ```bash
   cd /home/koogs/Documents/Mirror/speech-analyzer
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. Ensure your `.env` file has your Deepgram API key:
   ```
   DEEPGRAM_API_KEY=your_deepgram_api_key_here
   ```

3. Choose one of the following server options:

   **Option A: HTTP Server (Original)**
   ```bash
   python web_server/esp32_receiver.py
   ```

   **Option B: WebSocket Server**
   ```bash
   python web_server/esp32_receiver_websocket.py
   ```

   **Option C: Simple HTTP Server (Most Firewall Compatible)**
   ```bash
   python web_server/simple_esp32_receiver.py
   ```

   The server will start and show its IP address (e.g., `Running on http://192.168.50.130:8000`)

### 2. ESP32 Setup

**For HTTP Server (Option A):**
1. Open `esp32/esp32_audio_capture/esp32_audio_capture.ino` in Arduino IDE
2. Upload the code to your ESP32

**For WebSocket Server (Option B):**
1. Open `esp32/esp32_audio_capture_websocket/esp32_audio_capture_websocket.ino` in Arduino IDE
2. Upload the code to your ESP32

**For Simple HTTP Server (Option C - Most Compatible with Firewalls):**
1. Open `esp32/simple_esp32_audio_capture/simple_esp32_audio_capture.ino` in Arduino IDE
2. Upload the code to your ESP32

**Note:** All ESP32 sketches are already configured with your WiFi credentials and IP settings.

### 3. Wiring

Connect your INMP441 I2S microphone to the ESP32:

- VCC → 3.3V
- GND → GND
- WS → GPIO 25
- SD → GPIO 16
- SCK → GPIO 17

### 4. Operation

1. Start the laptop server (step 1.3 above)
2. Power on the ESP32 with the uploaded firmware
3. The ESP32 will connect to WiFi and start sending audio data to your laptop
4. The laptop will process the audio and save results to the `recordings/` directory
5. Check the server console for processing results

## Troubleshooting

- **Connection Issues**: Verify WiFi credentials and that the server IP address is correct
- **Audio Quality**: Ensure proper wiring and that the INMP441 is powered correctly
- **Server Not Responding**: Check that the firewall allows connections on port 8000
- **High Latency**: Try reducing the buffer size in the ESP32 code if needed

## Notes

- The ESP32 captures audio at 16kHz sample rate (matching the INMP441 capabilities)
- Audio is sent in chunks to the laptop for processing
- Each successful audio transmission results in a saved recording with analysis in the `recordings/` directory