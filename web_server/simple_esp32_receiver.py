"""
Simple HTTP Server for ESP32 Audio Reception
Receives audio data from ESP32 over WiFi via simple HTTP POST and processes it with the speech analyzer
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
import logging

from dotenv import load_dotenv
load_dotenv()

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.deepgram_client import DeepgramClientWrapper
from analysis.speech_analyzer import SpeechAnalyzer
from utils.logger import setup_logger
from utils.recording_manager import RecordingManager

# Disable Flask's default logger to reduce noise
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

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
            body {
                font-family: Arial, sans-serif;
                margin: 40px;
                background-color: #f4f4f4;
            }
            .container {
                max-width: 800px;
                margin: 0 auto;
                background-color: white;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 0 10px rgba(0,0,0,0.1);
            }
            .status {
                padding: 10px;
                margin: 10px 0;
                border-radius: 5px;
                font-weight: bold;
            }
            .connected {
                background-color: #d4edda;
                color: #155724;
            }
            .disconnected {
                background-color: #f8d7da;
                color: #721c24;
            }
            .options {
                margin: 20px 0;
            }
            .option-btn {
                display: block;
                width: 100%;
                padding: 15px;
                margin: 10px 0;
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                font-size: 16px;
                text-align: left;
            }
            .option-btn:hover {
                background-color: #0056b3;
            }
            .results {
                background-color: #f8f9fa;
                padding: 15px;
                margin: 15px 0;
                border-radius: 5px;
                max-height: 300px;
                overflow-y: auto;
            }
            .result-item {
                margin-bottom: 10px;
                padding: 10px;
                background-color: #e9ecef;
                border-radius: 5px;
            }
            h1 {
                color: #333;
                text-align: center;
            }
            .esp32-status {
                text-align: center;
                padding: 10px;
                margin: 10px 0;
                background-color: #e7f3ff;
                border-radius: 5px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>ESP32 Speech Analyzer</h1>

            <div class="esp32-status">
                <strong>ESP32 Status:</strong>
                <span id="esp32-connected" style="color: green;">Connected</span>
            </div>

            <div class="status connected">
                <strong>Status:</strong> Ready to receive audio from ESP32
            </div>

            <div class="options">
                <h2>Options:</h2>
                <button class="option-btn" onclick="analyzeSpeech(false)">1. Analyze speech (with prompt, not saved)</button>
                <button class="option-btn" onclick="analyzeSpeech(true)">2. Analyze speech (with prompt, saved)</button>
                <button class="option-btn" onclick="analyzeFreeSpeech()">3. Analyze free speech (no prompt, saved)</button>
                <button class="option-btn" onclick="playbackRecordings()">4. Playback recordings</button>
            </div>

            <h2>Recent Analyses</h2>
            <div id="results-container" class="results">
                <p>No analyses yet. ESP32 audio will appear here when received.</p>
            </div>

            <h2>Recorded Audio Files</h2>
            <div id="recordings-container" class="results">
                <p>Loading recorded files...</p>
            </div>

            <h2>Live Audio Stream</h2>
            <div class="results">
                <button id="startStreamBtn" onclick="startLiveStream()" style="background-color: #28a745; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; margin-right: 10px;">Start Live Stream</button>
                <button id="stopStreamBtn" onclick="stopLiveStream()" style="background-color: #dc3545; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer;">Stop Live Stream</button>
                <br><br>
                <audio id="liveAudio" controls style="width: 100%;">
                    Your browser does not support the audio element.
                </audio>
                <p id="streamStatus">Live stream not active</p>
            </div>

            <h2>System Info</h2>
            <p><strong>Laptop IP:</strong> 10.42.0.1 (WiFi on ubuntu hotspot)</p>
            <p><strong>Listening on port:</strong> 8000</p>
            <p><strong>Expected ESP32 IP:</strong> 10.42.0.156</p>
        </div>

        <script>
            // Function to add a result to the display
            function addResult(result) {
                const container = document.getElementById('results-container');

                const resultDiv = document.createElement('div');
                resultDiv.className = 'result-item';

                resultDiv.innerHTML = `
                    <strong>Analysis Result (${new Date().toLocaleTimeString()}):</strong><br>
                    <strong>Transcription:</strong> ${result.transcription || 'No transcription'}<br>
                    <strong>Analysis:</strong> Overall score: ${(result.analysis_results ? Object.values(result.analysis_results).filter(v => typeof v === 'number').reduce((a, b) => a + b, 0) / Object.values(result.analysis_results).filter(v => typeof v === 'number').length : 0).toFixed(1)}/10<br>
                    <small>Saved as: ${result.recording_saved || 'N/A'}</small>
                `;

                // Add to the top of the container
                container.insertBefore(resultDiv, container.firstChild);

                // Limit to 10 results
                if (container.children.length > 10) {
                    container.removeChild(container.lastChild);
                }
            }

            // Placeholder functions for the buttons
            function analyzeSpeech(save) {
                alert((save ? 'Saved' : 'Unsaved') + ' speech analysis would start now. This would trigger the ESP32 to begin recording.');
            }

            function analyzeFreeSpeech() {
                alert('Free speech analysis would start now. This would trigger the ESP32 to begin recording without a prompt.');
            }

            function playbackRecordings() {
                alert('Playback recordings would start now. This would show available recordings.');
            }

            // Listen for incoming audio data via server-sent events or polling
            // For now, we'll simulate by polling for recent results
            setInterval(fetchRecentResults, 5000);

            function fetchRecentResults() {
                // This would fetch recent results from the server
                // For now, we'll just log that we're checking
                console.log('Checking for new results...');
            }

            // Function to load and display recordings
            function loadRecordings() {
                fetch('/recordings')
                    .then(response => response.json())
                    .then(files => {
                        const container = document.getElementById('recordings-container');

                        if (files.length === 0) {
                            container.innerHTML = '<p>No recorded files yet.</p>';
                            return;
                        }

                        let html = '<table style="width:100%; border-collapse: collapse;">';
                        html += '<tr style="background-color: #ddd;"><th>Filename</th><th>Date</th><th>Size</th><th>Action</th></tr>';

                        files.forEach(file => {
                            html += `
                                <tr style="border-bottom: 1px solid #ccc;">
                                    <td>${file.filename}</td>
                                    <td>${file.modified}</td>
                                    <td>${(file.size / 1024).toFixed(2)} KB</td>
                                    <td>
                                        <button onclick="playAudio('${file.filename}')" style="background-color: #28a745; color: white; border: none; padding: 5px 10px; border-radius: 3px; cursor: pointer;">Play</button>
                                    </td>
                                </tr>
                            `;
                        });

                        html += '</table>';
                        container.innerHTML = html;
                    })
                    .catch(error => {
                        console.error('Error loading recordings:', error);
                        document.getElementById('recordings-container').innerHTML = '<p>Error loading recordings.</p>';
                    });
            }

            // Function to play audio
            function playAudio(filename) {
                const audio = new Audio(`/play/${filename}`);
                audio.play().catch(error => {
                    console.error('Error playing audio:', error);
                    alert('Error playing audio: ' + error.message);
                });
            }

            // Variables for live streaming
            let liveStreaming = false;
            let lastPlayedFile = '';
            let streamInterval;

            // Function to start live stream
            function startLiveStream() {
                liveStreaming = true;
                document.getElementById('streamStatus').textContent = 'Live stream active - playing latest audio';
                document.getElementById('startStreamBtn').disabled = true;
                document.getElementById('stopStreamBtn').disabled = false;

                // Start checking for new audio files every 2 seconds
                streamInterval = setInterval(checkForNewAudio, 2000);
            }

            // Function to stop live stream
            function stopLiveStream() {
                liveStreaming = false;
                document.getElementById('streamStatus').textContent = 'Live stream stopped';
                document.getElementById('startStreamBtn').disabled = false;
                document.getElementById('stopStreamBtn').disabled = true;

                clearInterval(streamInterval);

                // Stop the audio
                const audioElement = document.getElementById('liveAudio');
                audioElement.pause();
                audioElement.src = '';
            }

            // Function to check for new audio files and play them
            function checkForNewAudio() {
                if (!liveStreaming) return;

                fetch('/recordings')
                    .then(response => response.json())
                    .then(files => {
                        if (files.length > 0) {
                            // Get the most recent file
                            const latestFile = files[0];

                            // Play it if it's different from the last played file
                            if (latestFile.filename !== lastPlayedFile) {
                                lastPlayedFile = latestFile.filename;

                                const audioElement = document.getElementById('liveAudio');
                                audioElement.src = `/play/${latestFile.filename}`;
                                audioElement.load();
                                audioElement.play().catch(e => console.log('Auto-play prevented by browser policy'));

                                console.log(`Playing new audio: ${latestFile.filename}`);
                            }
                        }
                    })
                    .catch(error => {
                        console.error('Error checking for new audio:', error);
                    });
            }

            // Load recordings when page loads and refresh every 10 seconds
            document.addEventListener('DOMContentLoaded', function() {
                loadRecordings();
                setInterval(loadRecordings, 10000); // Refresh every 10 seconds

                // Initialize buttons
                document.getElementById('stopStreamBtn').disabled = true;
            });

            // WebSocket connection to receive real-time updates
            // Try to connect to the audio WebSocket if available
            try {
                const ws = new WebSocket('ws://' + window.location.hostname + ':8000/ws');
                ws.onmessage = function(event) {
                    const data = JSON.parse(event.data);
                    addResult(data);
                };
            } catch(e) {
                console.log('WebSocket not available, using polling');
            }
        </script>
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
            logger.error("Failed to process audio - transcription or analysis_results is None")
            return jsonify({"error": "Failed to process audio", "details": "Transcription or analysis failed"}), 500
        
        # Create recordings directory if it doesn't exist
        import os
        os.makedirs("recordings", exist_ok=True)

        # Save the raw audio received from ESP32
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        raw_audio_filename = f"esp32_raw_audio_{timestamp}"

        # Save raw audio file
        raw_audio_path = f"recordings/{raw_audio_filename}.wav"
        with open(raw_audio_path, "wb") as f:
            f.write(wav_data)
        print(f"Raw audio saved to: {raw_audio_path}")

        # Save the recording with analysis results
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
    if len(raw_data) < 8:  # Need at least 2 32-bit samples
        logger.warning(f"Audio data too short: {len(raw_data)} bytes")
        return b""

    # Convert raw bytes to 32-bit integers
    samples = struct.unpack('<{}i'.format(len(raw_data)//4), raw_data)

    # Extract 24-bit values from 32-bit containers (INMP441 packs 24-bit in 32-bit slots)
    # Shift right by 8 bits to get the actual 24-bit values
    adjusted_samples = [(sample >> 8) for sample in samples]

    # Convert to 16-bit values (divide by 256 to fit in 16-bit range)
    int16_samples = [max(-32768, min(32767, sample // 256)) for sample in adjusted_samples]

    # Apply more aggressive audio processing to improve quality
    # First, normalize the audio to use full dynamic range
    if int16_samples:
        max_val = max(max(int16_samples), abs(min(int16_samples)))
        if max_val > 0:
            # Normalize to use full 16-bit range
            normalized_samples = [int(val * 32767.0 / max_val) for val in int16_samples]
        else:
            normalized_samples = int16_samples
    else:
        logger.warning("No audio samples to process")
        return b""

    # Apply light noise reduction by setting very quiet samples to zero
    threshold = 50  # Samples below this level are considered noise
    filtered_samples = [val if abs(val) > threshold else 0 for val in normalized_samples]

    # Create WAV file in memory
    wav_buffer = BytesIO()
    with wave.open(wav_buffer, 'wb') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(16000)  # 16kHz sample rate
        wav_file.writeframes(struct.pack('<{}h'.format(len(filtered_samples)), *filtered_samples))

    # Return the WAV data as bytes
    wav_buffer.seek(0)
    return wav_buffer.read()

async def process_audio(wav_data):
    """
    Process WAV audio data using the speech analyzer
    """
    try:
        # Log audio data size for debugging
        logger.info(f"Processing WAV data of size: {len(wav_data)} bytes")

        # Transcribe audio using Deepgram
        logger.info("Transcribing audio using Deepgram...")
        transcription = await dg_client.transcribe_audio_from_bytes(wav_data)

        if not transcription:
            logger.error("Failed to get transcription from Deepgram - received empty transcription")
            logger.error(f"Audio data length: {len(wav_data)} bytes")
            return None, None

        logger.info(f"Transcription received: '{transcription}'")

        # For speech analysis without original prompt, pass None as second parameter
        analysis_results = speech_analyzer.analyze_speech(transcription, None)

        logger.info(f"Speech analysis completed. Results: {analysis_results}")
        return transcription, analysis_results

    except Exception as e:
        logger.error(f"Error in audio processing: {str(e)}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return None, None

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "ESP32 Speech Analyzer Receiver"})

@app.route('/test', methods=['POST'])
def test_connection():
    """Simple test endpoint to verify connectivity"""
    return jsonify({"status": "connected", "message": "ESP32 can reach the server"})

@app.route('/recordings')
def list_recordings():
    """List all recorded audio files"""
    import os
    recording_dir = "recordings"
    if not os.path.exists(recording_dir):
        os.makedirs(recording_dir)

    files = []
    for filename in os.listdir(recording_dir):
        if filename.endswith('.wav'):
            filepath = os.path.join(recording_dir, filename)
            mod_time = os.path.getmtime(filepath)
            size = os.path.getsize(filepath)
            files.append({
                'filename': filename,
                'modified': datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d %H:%M:%S'),
                'size': size
            })

    # Sort by modification time (newest first)
    files.sort(key=lambda x: x['modified'], reverse=True)
    return jsonify(files)

@app.route('/play/<filename>')
def play_recording(filename):
    """Serve a recorded audio file"""
    import os
    from flask import send_file

    # Security check: only allow .wav files
    if not filename.endswith('.wav'):
        return "Invalid file type", 400

    filepath = os.path.join("recordings", filename)
    if not os.path.exists(filepath):
        return "File not found", 404

    return send_file(filepath, as_attachment=False, mimetype='audio/wav')

if __name__ == '__main__':
    print("Starting Simple ESP32 Audio Receiver Server...")
    print("Make sure your ESP32 is configured to send audio data to this server")
    app.run(host='0.0.0.0', port=8000, debug=False)