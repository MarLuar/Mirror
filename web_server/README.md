# ESP32 Audio Collection System

This project enables audio collection from an ESP32 microcontroller and processing with advanced speech analysis.

## Components

1. **ESP32 Device**: Captures audio from I2S microphone and streams to server
2. **Web Server**: Receives audio data and processes with speech analyzer
3. **Speech Analyzer**: Provides phoneme alignment and pronunciation scoring

## Free Deployment Options

### Option 1: Render.com (Recommended)
1. Fork this repository to GitHub
2. Sign up at https://render.com
3. Create a new Web Service
4. Connect to your forked repository
5. Use the Dockerfile in `web_server/`
6. Set environment variables:
   - `DEEPGRAM_API_KEY`: Your Deepgram API key

### Option 2: Railway.app
1. Install Railway CLI or connect GitHub
2. Deploy the repository
3. Use the Dockerfile in `web_server/`
4. Add environment variables

### Option 3: Heroku (Paid after free tier)
1. Install Heroku CLI
2. Create app: `heroku create your-app-name`
3. Set buildpack: `heroku buildpacks:set heroku/python`
4. Deploy: `git push heroku main`

## ESP32 Setup

1. Install Arduino IDE or PlatformIO
2. Install ESP32 board support
3. Install I2S microphone (e.g., INMP441)
4. Update WiFi credentials in `esp32/audio_collector.ino`
5. Update server URL to your deployed endpoint
6. Upload to ESP32

## Hardware Connections (INMP441 to ESP32)
- VCC → 3.3V
- GND → GND
- SD → GPIO13
- WS/LRCK → GPIO15
- SCK/BCLK → GPIO14
- MCLK → GPIO0 (if required by your mic)

## Environment Variables
- `DEEPGRAM_API_KEY`: Required for transcription (get from deepgram.com)

## API Endpoints
- `POST /audio`: Receive audio data from ESP32
- `GET /health`: Health check
- `GET /`: Status page

## Notes
- The free tier on most platforms has limitations (sleep modes, request timeouts)
- For continuous operation, consider a Raspberry Pi or paid hosting
- Audio quality depends on microphone and environment