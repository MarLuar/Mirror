#!/bin/bash
# Script to start the ESP32 speech analyzer receiver

cd "$(dirname "$0")"

# Activate virtual environment
source venv/bin/activate

# Start the ESP32 receiver server
python web_server/esp32_receiver.py