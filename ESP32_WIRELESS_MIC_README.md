# Integrated Speech Analyzer with ESP32 Wireless Microphone Support

This project combines the original speech analysis features with ESP32 audio input via UDP, creating a wireless microphone system.

## Features

- Original speech analysis functionality (microphone input)
- ESP32 wireless microphone support via UDP
- Real-time audio streaming from ESP32
- Speech transcription and analysis
- Recording and playback capabilities

## Setup

### ESP32 Configuration

1. Upload the `esp32_i2s_audio_udp_hotspot.ino` sketch to your ESP32
2. Update the WiFi credentials and target IP address in the sketch:
   ```cpp
   const char* ssid = "your_wifi_ssid";
   const char* password = "your_wifi_password";
   const char* udpAddress = "your_computer_ip_address";  // Change this to your computer's IP
   const int udpPort = 1234;
   ```
3. Connect your I2S microphone to the ESP32:
   - WS: GPIO 17
   - SCK: GPIO 25
   - SD: GPIO 16

### Software Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set up your Deepgram API key in `.env`:
   ```
   DEEPGRAM_API_KEY=your_api_key_here
   ```

## Usage

Run the integrated application:
```bash
python integrated_speech_analyzer.py
```

The application provides the following options:
1. Analyze speech (with prompt, not saved) - Microphone
2. Analyze speech (with prompt, saved) - Microphone
3. Analyze free speech (no prompt, saved) - Microphone
4. Analyze speech from ESP32 (10 seconds)
5. Analyze speech from ESP32 (custom duration)
6. Playback recordings
7. Exit

## How It Works

1. The ESP32 captures audio from an I2S microphone
2. Audio is streamed via UDP to your computer on port 1234
3. The integrated application receives the UDP packets
4. Audio data is buffered and sent to Deepgram for transcription
5. Transcription results are analyzed and scored
6. Results are displayed and optionally saved

## Audio Format

The ESP32 sends audio in the following format:
- Sample Rate: 44.1 kHz
- Channels: 2 (Stereo)
- Bit Depth: 16-bit
- Format: Raw PCM data via UDP

## Troubleshooting

- Ensure your firewall allows UDP traffic on port 1234
- Verify the ESP32 and computer are on the same network
- Check that the IP address in the ESP32 sketch matches your computer's IP
- Make sure the Deepgram API key is properly set in the .env file