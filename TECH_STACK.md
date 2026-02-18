# ESP32 Wireless Microphone System with Speech Analysis

A comprehensive speech analysis system that combines ESP32 wireless microphone input with real-time transcription and analysis capabilities.

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
- **I2S Audio Interface** - Digital audio communication protocol

### Audio Processing
- **PyAudio** - Audio I/O operations
- **Wave Module** - Audio file format handling
- **SoundDevice** - Cross-platform audio library
- **I2S Protocol** - Digital audio transmission

### Networking & Communication
- **UDP Protocol** - Real-time audio streaming from ESP32
- **WiFi** - Wireless communication between ESP32 and host
- **Socket Programming** - Network communication layer

### Data Processing & Utilities
- **NumPy** - Numerical computations for audio analysis
- **JSON** - Configuration and data serialization
- **PIL (Pillow)** - Image processing for OLED display
- **RegEx** - Text processing and validation

### Development & Environment
- **Python-dotenv** - Environment variable management
- **Logging Module** - Application logging and debugging
- **Threading** - Concurrent operations support
- **Datetime** - Time and date handling

### Configuration & Storage
- **JSON Files** - Configuration storage
- **WAV Audio Format** - Audio file handling
- **CSV** - Data export capabilities (future)

## Architecture Components

### ESP32 Firmware
- **Arduino IDE Compatible** - ESP-IDF framework
- **I2S Audio Capture** - Real-time audio sampling
- **UDP Streaming** - Network audio transmission
- **OLED Display Control** - Visual feedback system
- **WiFi Integration** - Network connectivity

### Python Application
- **Integrated Speech Analysis** - Core application logic
- **UDP Audio Receiver** - Real-time audio capture
- **Deepgram Client Wrapper** - API abstraction layer
- **Microphone Handler** - Local audio input
- **Speech Analyzer** - Analysis algorithms
- **Prompt Manager** - Text prompt handling
- **Recording Manager** - Audio file management
- **OLED Display** - Visual feedback system

## Features

- Real-time wireless audio streaming from ESP32
- Live speech analysis with multiple metrics
- Prompt-based speech evaluation
- OLED display integration for ESP32
- Audio recording and playback capabilities
- Configurable network settings
- Comprehensive scoring system

## Setup Requirements

### Hardware
- ESP32 development board
- INMP441 I2S digital microphone
- SSD1306 OLED display (optional)
- USB-C cable for ESP32 programming

### Software Dependencies
- Python 3.12+
- Required Python packages (see requirements.txt)
- Arduino IDE (for ESP32 programming)
- Deepgram API key

## Installation

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

## License

[Specify license type here]