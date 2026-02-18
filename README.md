# ESP32 Wireless Microphone System

A comprehensive speech analysis system that combines ESP32 wireless microphone input with real-time transcription and analysis capabilities.

## Features

- Real-time wireless audio streaming from ESP32
- Live speech analysis with multiple metrics (pronunciation, articulation, pace, clarity)
- Prompt-based speech evaluation
- OLED display integration for ESP32
- Audio recording and playback capabilities
- Configurable network settings
- Comprehensive scoring system

## Technology Stack

### Programming Languages
- **Python 3.12+** - Core application development
- **C++** - ESP32 Arduino firmware development
- **JavaScript** - Web interface components (optional)
- **JSON** - Configuration and data exchange format

### Backend & Application Framework
- **Pygame** - Audio handling and system interface
- **AsyncIO** - Asynchronous programming for concurrent operations
- **Socket Programming** - UDP networking for ESP32 communication

### Speech Recognition & Analysis
- **Deepgram API** - Advanced speech-to-text transcription
- **Deepgram Python SDK** - API integration for audio processing
- **Custom Speech Analyzer** - Local analysis of pronunciation, articulation, pace, clarity

### Hardware Integration
- **ESP32** - Microcontroller for wireless audio capture
- **INMP441 I2S Digital Microphone** - High-quality audio input
- **SSD1306 OLED Display** - Visual feedback and status display

### Audio Processing
- **PyAudio, SoundDevice** - Audio I/O operations
- **Wave Module** - Audio file format handling
- **I2S Protocol** - Digital audio transmission

### Networking & Communication
- **UDP Protocol** - Real-time audio streaming from ESP32
- **WiFi** - Wireless communication between ESP32 and host

## Hardware Requirements

- ESP32 development board
- INMP441 I2S digital microphone
- SSD1306 OLED display (optional)
- USB-C cable for ESP32 programming

## Setup

1. Clone the repository
2. Install Python dependencies: `pip install -r requirements.txt`
3. Set up your Deepgram API key in `.env` file
4. Configure ESP32 firmware with correct network settings
5. Update `config.json` with your network configuration

## Usage

Run the main application:
```bash
python integrated_speech_analyzer.py
```

Select from various speech analysis modes:
- Standard microphone analysis
- ESP32 wireless microphone analysis
- Prompt-based evaluation
- Free speech analysis
- Audio playback

## Configuration

The system uses `config.json` for configuration:
- ESP32 IP address and ports
- Recording settings
- Analysis aspects to evaluate
- API timeout settings

## Project Structure

- `integrated_speech_analyzer.py` - Main application entry point
- `api/deepgram_client.py` - Deepgram API integration
- `audio/microphone.py` - Audio input handling
- `analysis/speech_analyzer.py` - Speech analysis algorithms
- `utils/` - Utility modules (prompter, recording manager, OLED display)
- `speech_to_textESP32/` - ESP32 firmware and related code
- `web_server/` - Web interface components

## License

[Specify license type here]