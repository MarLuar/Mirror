#!/bin/bash
# Script to run the ESP32 Speech-to-Text application

# Activate virtual environment
source venv/bin/activate

# Check if DEEPGRAM_API_KEY is set
if [ -z "$DEEPGRAM_API_KEY" ]; then
    echo "Error: DEEPGRAM_API_KEY environment variable not set!"
    echo "Please set your Deepgram API key:"
    echo "export DEEPGRAM_API_KEY='your_api_key_here'"
    exit 1
fi

echo "Starting ESP32 Speech-to-Text application..."
echo "Access the web interface at http://localhost:5000"
echo "Make sure your ESP32 is sending audio to this computer's IP on port 1234"

# Run the application
python web_interface.py