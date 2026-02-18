"""
ESP32 Audio Receiver and Speech Analyzer Server
Receives audio data from ESP32 over WiFi and processes it with the speech analyzer
"""
import asyncio
import json
import os
from datetime import datetime
from io import BytesIO
import wave
import struct
from flask import Flask, request, jsonify, render_template_string
from werkzeug.utils import secure_filename
import numpy as np

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from api.deepgram_client import DeepgramClientWrapper
from analysis.speech_analyzer import SpeechAnalyzer
from utils.logger import setup_logger
from utils.recording_manager import RecordingManager

# Initialize Flask app
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

# Initialize speech analysis components
logger = setup_logger(__name__)
dg_client = DeepgramClientWrapper(os.getenv('DEEPGRAM_API_KEY'))
speech_analyzer = SpeechAnalyzer()
recording_manager = RecordingManager()

@app.route('/')
def index():
    """Main page showing status and controls"""
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>ESP32 Speech Analyzer</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .status { padding: 10px; margin: 10px 0; border-radius: 5px; }
            .connected { background-color: #d4edda; color: #155724; }
            .disconnected { background-color: #f8d7da; color: #721c24; }
            .results { background-color: #f8f9fa; padding: 15px; margin: 15px 0; border-radius: 5px; }
        </style>
    </head>
    <body>
        <h1>ESP32 Speech Analyzer</h1>
        <div class="status connected">
            <strong>Status:</strong> Ready to receive audio from ESP32
        </div>
        <p>ESP32 should send audio data to: <code>{{ request.host_url }}audio</code></p>
        <h2>Recent Analyses</h2>
        <div id="recent-results"></div>
    </body>
    </html>
    """
    return render_template_string(html_template)

@app.route('/audio', methods=['POST'])
def receive_audio():
    """Receive raw audio data from ESP32 and process it"""
    try:
        # Get raw audio data from request
        audio_data = request.data
        
        if not audio_data:
            return jsonify({"error": "No audio data received"}), 400
            
        logger.info(f"Received {len(audio_data)} bytes of audio data from ESP32")
        
        # Convert raw 32-bit integer data to WAV format
        wav_data = convert_i2s_to_wav(audio_data)
        
        # Process the audio with speech analyzer
        transcription, analysis_results = asyncio.run(process_audio(wav_data))
        
        if transcription is None or analysis_results is None:
            return jsonify({"error": "Failed to process audio"}), 500
        
        # Save the recording with analysis results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        recording_filename = f"esp32_speech_{timestamp}"
        audio_params = {
            'channels': 1,
            'sample_width': 2,  # 16-bit
            'framerate': 16000
        }
        recording_path = recording_manager.save_recording(
            wav_data,
            recording_filename,
            audio_params,
            analysis_results,
            transcription
        )
        
        # Prepare response
        response_data = {
            "status": "success",
            "transcription": transcription,
            "analysis_results": analysis_results,
            "recording_saved": os.path.basename(recording_path)
        }
        
        logger.info(f"Audio processed successfully. Transcription: {transcription[:50]}...")
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Error processing audio from ESP32: {str(e)}")
        return jsonify({"error": f"Error processing audio: {str(e)}"}), 500

def convert_i2s_to_wav(raw_data):
    """
    Convert raw I2S data from ESP32 to WAV format
    ESP32 sends 32-bit integers, but INMP441 has 24-bit resolution
    """
    # Convert raw bytes to 32-bit integers
    samples = struct.unpack('<{}i'.format(len(raw_data)//4), raw_data)
    
    # Extract 24-bit values from 32-bit containers (INMP441 packs 24-bit in 32-bit slots)
    # Shift right by 8 bits to get the actual 24-bit values
    adjusted_samples = [(sample >> 8) for sample in samples]
    
    # Convert to 16-bit values (divide by 256 to fit in 16-bit range)
    int16_samples = [max(-32768, min(32767, sample // 256)) for sample in adjusted_samples]
    
    # Create WAV file in memory
    wav_buffer = BytesIO()
    with wave.open(wav_buffer, 'wb') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(16000)  # 16kHz sample rate
        wav_file.writeframes(struct.pack('<{}h'.format(len(int16_samples)), *int16_samples))
    
    # Return the WAV data as bytes
    wav_buffer.seek(0)
    return wav_buffer.read()

async def process_audio(wav_data):
    """
    Process WAV audio data using the speech analyzer
    """
    try:
        # Transcribe audio using Deepgram
        logger.info("Transcribing audio using Deepgram...")
        transcription = await dg_client.transcribe_audio_from_bytes(wav_data)
        
        if not transcription:
            logger.error("Failed to get transcription from Deepgram")
            return None, None
        
        # For speech analysis without original prompt, pass None as second parameter
        analysis_results = speech_analyzer.analyze_speech(transcription, None)
        
        logger.info(f"Speech analysis completed. Results: {analysis_results}")
        return transcription, analysis_results
        
    except Exception as e:
        logger.error(f"Error in audio processing: {str(e)}")
        return None, None

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "ESP32 Speech Analyzer Receiver"})

if __name__ == '__main__':
    print("Starting ESP32 Audio Receiver Server...")
    print("Make sure your ESP32 is configured to send audio data to this server")
    app.run(host='0.0.0.0', port=8000, debug=False)