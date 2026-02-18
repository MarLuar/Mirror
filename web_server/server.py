"""
Web server to receive audio from ESP32 and process with speech analyzer
Deploy this on a free hosting service like Render, Railway, or Heroku
"""

from flask import Flask, request, jsonify
import tempfile
import os
import subprocess
import threading
import time
from datetime import datetime
import wave
import io

# Import your speech analyzer
from analysis.speech_analyzer import SpeechAnalyzer
from api.deepgram_client import DeepgramClientWrapper
from utils.prompter import TextPrompter
from utils.logger import setup_logger

app = Flask(__name__)
logger = setup_logger(__name__)

# Initialize components
analyzer = SpeechAnalyzer()
prompter = TextPrompter()

@app.route('/')
def home():
    return '''
    <html>
        <body>
            <h1>ESP32 Audio Receiver</h1>
            <p>This server receives audio data from ESP32 and processes it with speech analysis.</p>
            <p>Send POST requests to /audio with audio data.</p>
        </body>
    </html>
    '''

@app.route('/audio', methods=['POST'])
def receive_audio():
    try:
        # Get raw audio data from request
        audio_data = request.data
        
        if not audio_data:
            return jsonify({"error": "No audio data received"}), 400
        
        logger.info(f"Received audio data: {len(audio_data)} bytes")
        
        # Create a temporary WAV file with proper headers
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
            # Create WAV file with proper format
            with wave.open(temp_wav.name, 'wb') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(16000)  # 16kHz (ESP32 sample rate)
                wav_file.writeframes(audio_data)
            
            # Process the audio file with your speech analyzer
            result = process_audio_file(temp_wav.name)
            
            # Clean up temporary file
            os.unlink(temp_wav.name)
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error processing audio: {str(e)}")
        return jsonify({"error": f"Processing failed: {str(e)}"}), 500

def process_audio_file(wav_file_path):
    """Process the WAV file with your speech analyzer"""
    try:
        # For demonstration, we'll use a simple prompt
        # In practice, you might want to send the prompt from ESP32 or use a default
        prompt_text = "Please speak clearly into the microphone"
        
        # Read the audio file as bytes
        with open(wav_file_path, 'rb') as f:
            audio_bytes = f.read()
        
        # Simulate transcription (in real implementation, you'd send to Deepgram)
        # For demo purposes, we'll create a mock transcription
        mock_transcription = "This is a sample transcription from ESP32 audio"
        
        # Analyze the "transcription" using your analyzer
        # Note: This is simplified - in practice you'd transcribe the audio first
        analysis_results = analyzer.analyze_speech(mock_transcription, prompt_text)
        
        # Return analysis results
        result = {
            "timestamp": datetime.now().isoformat(),
            "analysis": analysis_results,
            "message": "Audio processed successfully",
            "prompt_used": prompt_text
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Error in process_audio_file: {str(e)}")
        raise

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

if __name__ == '__main__':
    # For local testing
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)