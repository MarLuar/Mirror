# ESP32 Speech-to-Text with Deepgram Integration

This project integrates an ESP32 microphone with Deepgram's real-time speech-to-text API, allowing you to stream audio from the ESP32 and get live transcriptions via a web interface.

## Prerequisites

1. **Hardware Setup**:
   - ESP32 board with I2S microphone (INMP441 or similar)
   - Proper wiring as defined in the Arduino sketch

2. **Software Requirements**:
   - Python 3.7+
   - Deepgram API Key (get one free at [https://console.deepgram.com/signup](https://console.deepgram.com/signup))

## Installation

1. Clone or download this repository

2. Install dependencies:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install deepgram-sdk flask websockets
   ```

3. Upload the Arduino sketch to your ESP32:
   - Open `esp32_i2s_audio_udp_hotspot/esp32_i2s_audio_udp_hotspot.ino` in Arduino IDE
   - Update WiFi credentials and UDP destination IP in the sketch
   - Upload to your ESP32

## Configuration

1. Set your Deepgram API key as an environment variable:
   ```bash
   export DEEPGRAM_API_KEY="your_api_key_here"
   ```

2. Update the UDP destination IP in the ESP32 sketch to match your computer's IP address:
   ```cpp
   const char* udpAddress = "YOUR_COMPUTER_IP";  // Change this to your computer's IP
   ```

## Running the Application

1. Activate your virtual environment:
   ```bash
   source venv/bin/activate
   ```

2. Run the web interface:
   ```bash
   python web_interface.py
   ```

3. Access the web interface at [http://localhost:5000](http://localhost:5000)

4. Use the Start/Stop buttons to control the speech-to-text functionality

## How It Works

1. The ESP32 captures audio via the I2S microphone
2. Audio is streamed over UDP to your computer on port 1234
3. The Python application receives the UDP audio stream
4. Audio is forwarded to Deepgram's real-time transcription API
5. Transcriptions are sent back to the web interface via WebSocket
6. The web interface displays real-time transcriptions

## Troubleshooting

- If you don't see any transcriptions, check that:
  - The ESP32 is properly connected to WiFi
  - The UDP destination IP in the ESP32 sketch matches your computer's IP
  - Your firewall isn't blocking UDP traffic on port 1234
  - Your Deepgram API key is correctly set

- Check the console output for any error messages

## Files

- `web_interface.py` - Main application with Flask, WebSocket, and Deepgram integration
- `templates/index.html` - Web interface for controlling STT
- `esp32_i2s_audio_udp_hotspot/esp32_i2s_audio_udp_hotspot.ino` - Arduino sketch for ESP32
- `udp_audio_recorder.py` - Original UDP audio recorder (for reference)
- `udp_audio_recorder_timed.py` - Timed version of the recorder (for reference)