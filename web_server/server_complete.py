"""
Web server to receive audio from ESP32 and process with speech analyzer
Deploy this on a free hosting service like Render, Railway, or Heroku
"""

from flask import Flask, request, jsonify, send_from_directory
import tempfile
import os
import json
from datetime import datetime
import wave
import io
import threading
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import your speech analyzer components
from analysis.speech_analyzer import SpeechAnalyzer
from api.deepgram_client import DeepgramClientWrapper
from utils.prompter import TextPrompter
from utils.logger import setup_logger

app = Flask(__name__)
logger = setup_logger(__name__)

# Initialize components
analyzer = SpeechAnalyzer()
prompter = TextPrompter()

# Initialize Deepgram client if API key is available
dg_client = None
if os.getenv('DEEPGRAM_API_KEY'):
    dg_client = DeepgramClientWrapper(os.getenv('DEEPGRAM_API_KEY'))

@app.route('/')
def home():
    return '''
    <html>
        <body>
            <h1>ESP32 Audio Receiver</h1>
            <p>This server receives audio data from ESP32 and processes it with speech analysis.</p>
            <p>Send POST requests to /audio with audio data.</p>
            <p>Status: <span id="status">Operational</span></p>
            <script>
                setInterval(function() {
                    fetch('/health')
                    .then(response => response.json())
                    .then(data => {
                        document.getElementById('status').textContent = 'Operational';
                        document.getElementById('status').style.color = 'green';
                    })
                    .catch(error => {
                        document.getElementById('status').textContent = 'Error';
                        document.getElementById('status').style.color = 'red';
                    });
                }, 5000);
            </script>
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
        # Read the audio file as bytes
        with open(wav_file_path, 'rb') as f:
            audio_bytes = f.read()
        
        # If Deepgram client is available, transcribe the audio
        if dg_client:
            # Transcribe audio using Deepgram
            transcription = dg_client.transcribe_audio(audio_bytes)
        else:
            # Fallback if no API key
            transcription = "Transcription unavailable - no API key configured"
        
        # Use a default prompt for analysis (or you could send the prompt from ESP32)
        default_prompt = "Please speak clearly into the microphone for speech analysis"
        
        # Analyze the transcription using your analyzer
        analysis_results = analyzer.analyze_speech(transcription, default_prompt)
        
        # Return comprehensive results
        result = {
            "timestamp": datetime.now().isoformat(),
            "transcription": transcription,
            "analysis": analysis_results,
            "message": "Audio processed successfully",
            "prompt_used": default_prompt,
            "average_score": sum(analysis_results.values()) / len(analysis_results) if analysis_results else 0
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Error in process_audio_file: {str(e)}")
        raise

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy", 
        "timestamp": datetime.now().isoformat(),
        "deepgram_available": dg_client is not None
    })

@app.route('/api/config', methods=['GET'])
def get_config():
    """Get configuration information"""
    return jsonify({
        "sample_rate": 16000,
        "channels": 1,
        "bit_depth": 16,
        "timestamp": datetime.now().isoformat()
    })

if __name__ == '__main__':
    # For local testing
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)