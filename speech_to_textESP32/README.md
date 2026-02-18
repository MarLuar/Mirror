# ESP32 Speech-to-Text Recorder

This project creates a simple speech-to-text recorder using an ESP32 with I2S microphone input and SD card storage.

## Hardware Setup

### I2S Microphone Connection
- WS (Word Select) → GPIO 25
- SCK (Serial Clock) → GPIO 27
- SD (Data) → GPIO 14 (assumed, adjust if needed)

### SD Card Module Connection
- GND → GND
- VCC → VIN (5V)
- MISO → GPIO 19
- MOSI → GPIO 23
- SCK → GPIO 18
- CS → GPIO 5

### Button Connection
- Button → GPIO 14 (with pull-up resistor)

## WiFi Configuration

The code is pre-configured with:
- SSID: "Iphone SE"
- Password: "koogsthegroopa"

Update these values in the code if your network differs.

## Features

- Records audio for 2 seconds when button is pressed (reduced from 5s to save memory)
- Saves raw audio data to SD card with timestamp
- Prints audio statistics to serial monitor
- Connects to WiFi for potential online speech-to-text services
- Includes audio preprocessing (normalization, RMS calculation)
- Activity detection to only save meaningful recordings

## Usage

1. Upload the code to your ESP32
2. Open the Serial Monitor at 115200 baud
3. Press the button to start recording
4. Speak into the microphone for 5 seconds
5. Audio will be saved to SD card as a raw file
6. Check the serial output for details

## Notes

- The current implementation saves raw audio data to SD card
- Actual speech-to-text conversion would require sending the audio to an online service
- Adjust I2S_SD pin if your microphone module uses a different pin