#!/bin/bash
# Script to start the ESP32 speech analyzer receiver (WebSocket version)

cd "$(dirname "$0")"

# Activate virtual environment
source venv/bin/activate

# Start the ESP32 receiver server (WebSocket version)
python web_server/esp32_receiver_websocket.py