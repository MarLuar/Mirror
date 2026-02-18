#!/bin/bash

# Script to install required libraries for the ESP32 ElevenLabs STT project

echo "Installing required libraries..."

# Install ArduinoJson
echo "Installing ArduinoJson..."
pio lib install "bblanchon/ArduinoJson"

# Install SD library
echo "Installing SD library..."
pio lib install "adafruit/SD"

echo "Library installation complete!"
echo "You can now upload the project to your ESP32."