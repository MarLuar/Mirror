# ESP32 ElevenLabs Speech-to-Text Project

This project implements speech-to-text functionality using an ESP32 with an external I2S microphone and SD card storage, sending audio recordings to ElevenLabs for transcription.

## Hardware Setup

### Connections

#### SD Card Module to ESP32:
```
SD Card Module    ESP32
GND              GND
Vcc              VIn (or 3.3V)
MISO             D19
MOSI             D23
SCK              D18
CS               D5
```

#### I2S Microphone to ESP32:
```
I2S Microphone    ESP32
GND              GND
VDD              3.3V
WS/LRCK          D25
SCK/BCLK         D27
SD/DOUT          D26
```

#### Push Button to ESP32:
```
Push Button    ESP32
One leg        D14
Other leg      GND
```

## Software Setup

### Prerequisites

1. Install the Arduino IDE or PlatformIO
2. Add ESP32 board support to your development environment
3. Install the following libraries:
   - ArduinoJson
   - SD
   - SPI

### Configuration

Before uploading the code, you need to update the following values in the code (if you want to use different credentials):

1. `ssid` - Your WiFi network name
2. `password` - Your WiFi password
3. `elevenlabs_api_key` - Your ElevenLabs API key

Find these in the top section of the code:
```cpp
const char* ssid = "Iphone SE";         // Replace with your WiFi SSID
const char* password = "koogsthegroopa"; // Replace with your WiFi password
const char* elevenlabs_api_key = "sk_32ecab6e7915fe60d18bf5e3599c57bb7163d06b0c5e379b"; // Replace with your ElevenLabs API key
```

Note: The credentials have already been configured with your provided values.

### Uploading the Code

1. Connect your ESP32 to your computer via USB
2. Select the correct board and port in your development environment
3. Upload the code to your ESP32

## Usage

1. Power on the ESP32 - it will connect to WiFi
2. Press the button to start recording
3. Speak into the microphone while holding the button
4. Release the button to stop recording and send the audio to ElevenLabs
5. Check the serial monitor for the transcription result

## Troubleshooting

- If the SD card fails to initialize, check the wiring connections
- If WiFi connection fails, verify your credentials
- If transcription fails, check your ElevenLabs API key and internet connection
- If you see "Failed to allocate memory" errors, try reducing the recording time
- Monitor the serial output for detailed error messages

## Notes

- Recordings are saved to the SD card with timestamps
- Old recordings are automatically cleaned up
- Maximum recording time is now 5 seconds to prevent memory issues
- Files larger than 150KB will not be sent to ElevenLabs to preserve memory
- The "Failed to allocate memory" error occurs when the ESP32 runs out of heap memory
- If you get empty transcriptions, it might be due to low audio quality or silence in the recording

## Memory Optimization Tips

- Keep recordings short (under 5 seconds recommended)
- The ESP32 has limited RAM, so large audio files may cause allocation failures
- If you continue to have memory issues, consider using a more powerful ESP32 variant with PSRAM