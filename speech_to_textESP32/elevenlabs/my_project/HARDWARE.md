# ESP32 ElevenLabs STT Hardware Specifications

## Pin Assignments

| Component | ESP32 Pin | Description |
|-----------|-----------|-------------|
| I2S WS (Word Select) | GPIO 25 | I2S clock signal for word selection |
| I2S SCK (Serial Clock) | GPIO 27 | I2S bit clock signal |
| I2S SD (Serial Data) | GPIO 26 | I2S data output from microphone |
| SD Card MISO | GPIO 19 | SD card data input to ESP32 |
| SD Card MOSI | GPIO 23 | SD card data output from ESP32 |
| SD Card SCK | GPIO 18 | SD card clock signal |
| SD Card CS | GPIO 5 | SD card chip select |
| Button | GPIO 14 | Recording trigger button |

## Wiring Diagram

```
ESP32 DevKit Pinout Reference:

Upper row (GPIO):
D25  D26  D27  D14  D12  D13  D15  D2  D0  D4  D16  D17

Lower row (GPIO):
D33  D32  D35  D34  D39  D36  D5  D18  D19  D21  D22  D23

Power & Ground:
EN   3V3  GND  GND  TX0  RX0
VIN  GND  GND  GND  GND  GND
```

## Hardware Components

1. **ESP32 Development Board**
   - Any ESP32 variant with sufficient GPIO pins
   - Recommended: ESP32-DevKitC or similar

2. **I2S Digital Microphone**
   - Example: INMP441 or ICS-43434
   - Requires 3.3V power supply
   - Connect to GPIO 25 (WS), GPIO 27 (SCK), GPIO 26 (SD)

3. **SD Card Module**
   - Standard SPI interface
   - Connect to GPIO 19 (MISO), GPIO 23 (MOSI), GPIO 18 (SCK), GPIO 5 (CS)
   - Power with 3.3V

4. **Push Button**
   - Momentary switch
   - Connect one side to GPIO 14, other to GND
   - Internal pull-up resistor enabled in code

## Power Requirements

- Input voltage: 7-12V recommended (VIN pin)
- Operating voltage: 3.3V (regulated)
- Current draw: ~200mA during active recording

## Memory Usage

- Program storage: ~1.2MB
- Dynamic memory: ~150KB during operation
- SD card: At least 1GB capacity recommended

## Audio Specifications

- Sample rate: 16kHz (configurable)
- Bit depth: 16-bit
- Format: WAV (header added automatically)
- Max recording time: 30 seconds per session