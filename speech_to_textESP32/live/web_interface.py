#!/usr/bin/env python3
"""
Flask Web Interface for ESP32 Speech-to-Text Control
Provides a web interface to start/stop STT and display transcriptions
"""

import asyncio
import json
import os
import threading
from datetime import datetime
from queue import Queue

from flask import Flask, render_template
import websockets
from websockets.exceptions import ConnectionClosedOK
from deepgram import DeepgramClient


# Flask app setup
app = Flask(__name__, template_folder='templates')

# Global variables for STT functionality
dg_connection = None
is_listening = False
deepgram_client = None
websocket_connections = set()  # Track active WebSocket connections

# Queues for inter-thread communication
command_queue = Queue()
transcript_queue = Queue()


class UDPAudioReceiver:
    """Handles receiving audio data from ESP32 via UDP"""
    
    def __init__(self, host="0.0.0.0", port=1234):
        self.host = host
        self.port = port
        self.sock = None
        self.running = False
        self.audio_queue = Queue()
        
    def start(self):
        """Start the UDP receiver thread"""
        import socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.host, self.port))
        self.running = True
        
        print(f"UDP Audio Receiver listening on {self.host}:{self.port}")
        
        # Start receiving in a separate thread
        receive_thread = threading.Thread(target=self._receive_loop)
        receive_thread.daemon = True
        receive_thread.start()
        
    def _receive_loop(self):
        """Main receive loop"""
        while self.running:
            try:
                data, addr = self.sock.recvfrom(4096)
                if is_listening:
                    # Put audio data in queue for processing
                    self.audio_queue.put(data)
            except Exception as e:
                if self.running:  # Only log if we're supposed to be running
                    print(f"Error receiving UDP audio: {e}")
                    
    def stop(self):
        """Stop the UDP receiver"""
        self.running = False
        if self.sock:
            self.sock.close()
    
    def get_audio_data(self):
        """Get audio data from the queue"""
        if not self.audio_queue.empty():
            return self.audio_queue.get_nowait()
        return None


# Initialize UDP receiver
udp_receiver = UDPAudioReceiver()


def handle_transcript(result, **kwargs):
    """Handle transcript received from Deepgram"""
    try:
        sentence = result["channel"]["alternatives"][0]["transcript"]
        
        if len(sentence) == 0:
            return
        
        # Check if the result contains speech_final flag
        is_final = result.get("is_final", False)
        speech_final = result.get("speech_final", False)
        
        if is_final or speech_final:
            timestamp = datetime.now().strftime("%H:%M:%S")
            transcript = {
                "type": "transcript",
                "text": sentence,
                "timestamp": timestamp
            }
            transcript_queue.put(transcript)
            print(f"[{timestamp}] SPEAKER: {sentence}\n")
    except KeyError as e:
        print(f"Error parsing transcript: {e}")
        print(f"Result: {result}")


def handle_metadata(metadata, **kwargs):
    """Handle metadata received from Deepgram"""
    print(f"Metadata: {metadata}")


def handle_utterance_end(utterance_end, **kwargs):
    """Handle utterance end event from Deepgram"""
    print("Utterance ended")


def handle_speech_started(speech_started, **kwargs):
    """Handle speech started event from Deepgram"""
    print("Speech detected")


def handle_close(close, **kwargs):
    """Handle close event from Deepgram"""
    print("Connection closed")


def handle_error(error, **kwargs):
    """Handle error event from Deepgram"""
    print(f"Deepgram error: {error}")


def handle_unhandled(unhandled, **kwargs):
    """Handle unhandled event from Deepgram"""
    print(f"Unhandled event: {unhandled}")


# Global variable to hold the connection context
dg_connection_context = None
dg_socket_client = None


def connect_deepgram():
    """Connect to Deepgram WebSocket API"""
    global dg_connection_context, dg_socket_client, deepgram_client
    
    # Initialize Deepgram client
    api_key = os.environ.get("DEEPGRAM_API_KEY")
    
    if not api_key:
        print("DEEPGRAM_API_KEY environment variable not set!")
        return False
    
    try:
        # Create the Deepgram client
        deepgram_client = DeepgramClient(api_key=api_key)
        
        # Define the live transcription options
        dg_options = {
            "model": "nova-2",
            "language": "en-US",
            # Apply smart formatting to the output
            "smart_format": True,
            # To get UtteranceEnd, the following must be set:
            "interim_results": True,
            "utterance_end_ms": "1000",
            "vad_events": True,
            # Time in milliseconds of silence to wait for before finalizing speech
            "endpointing": "300",
        }
        
        # Store the connection context (this is a context manager)
        dg_connection_context = deepgram_client.listen.v1.connect(**dg_options)
        
        # Enter the context to get the socket client
        dg_socket_client = dg_connection_context.__enter__()
        
        # Set up event listeners
        dg_socket_client.on("Results", lambda result: handle_transcript(result=result))
        dg_socket_client.on("Metadata", lambda metadata: handle_metadata(metadata=metadata))
        dg_socket_client.on("UtteranceEnd", lambda utterance_end: handle_utterance_end(utterance_end=utterance_end))
        dg_socket_client.on("SpeechStarted", lambda speech_started: handle_speech_started(speech_started=speech_started))
        dg_socket_client.on("Close", lambda close: handle_close(close=close))
        dg_socket_client.on("Error", lambda error: handle_error(error=error))
        dg_socket_client.on("Unhandled", lambda unhandled: handle_unhandled(unhandled=unhandled))
        
        print("Connected to Deepgram WebSocket")
        return True
        
    except Exception as e:
        print(f"Error connecting to Deepgram: {e}")
        return False


def start_listening():
    """Start the listening process"""
    global is_listening
    if not is_listening:
        is_listening = True
        # Send status update to all WebSocket clients
        status_update = {
            "type": "status",
            "status": "Listening"
        }
        broadcast_to_clients(status_update)
        print("Started listening for audio...")


def stop_listening():
    """Stop the listening process"""
    global is_listening
    if is_listening:
        is_listening = False
        # Send status update to all WebSocket clients
        status_update = {
            "type": "status",
            "status": "Not Listening"
        }
        broadcast_to_clients(status_update)
        print("Stopped listening for audio...")


def broadcast_to_clients(message):
    """Send a message to all connected WebSocket clients"""
    if websocket_connections:
        # Convert dict to JSON string
        json_message = json.dumps(message)
        
        # Since we're in a different thread, we need to use the event loop
        # But for now, let's just store the message to be sent later
        # We'll handle this differently in the main loop
        pass  # We'll handle broadcasting differently


async def handle_websocket(websocket, path):
    """Handle incoming WebSocket connections"""
    # Add the new connection to our set
    websocket_connections.add(websocket)
    
    try:
        # Send initial status to the new client
        initial_status = {
            "type": "status",
            "status": "Listening" if is_listening else "Not Listening"
        }
        await websocket.send(json.dumps(initial_status))
        
        # Handle messages from the client
        async for message in websocket:
            try:
                data = json.loads(message)
                action = data.get('action')
                
                if action == 'start':
                    start_listening()
                elif action == 'stop':
                    stop_listening()
            except json.JSONDecodeError:
                print("Received invalid JSON from client")
            except Exception as e:
                print(f"Error processing WebSocket message: {e}")
    except ConnectionClosedOK:
        pass  # Normal closure
    finally:
        # Remove the connection from our set when it closes
        websocket_connections.discard(websocket)


@app.route('/')
def index():
    """Serve the main page"""
    return render_template('index.html')


def run_flask_app():
    """Run the Flask application"""
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)


def audio_stream_handler():
    """Continuously send audio data from UDP to Deepgram"""
    global is_listening, dg_socket_client
    
    while True:
        if is_listening and dg_socket_client:
            # Get audio data from UDP receiver
            audio_data = udp_receiver.get_audio_data()
            
            if audio_data:
                try:
                    # Send audio data to Deepgram
                    dg_socket_client.send_media(audio_data)
                except Exception as e:
                    print(f"Error sending audio to Deepgram: {e}")
        
        # Small delay to prevent busy-waiting
        import time
        time.sleep(0.01)


def run_websocket_server():
    """Run the WebSocket server in a separate thread"""
    def run_loop():
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Start the WebSocket server
        server = loop.run_until_complete(websockets.serve(handle_websocket, "0.0.0.0", 8765))
        print("WebSocket server started on ws://0.0.0.0:8765")
        
        # Run the event loop forever
        loop.run_forever()
    
    # Create and start the thread
    ws_thread = threading.Thread(target=run_loop, daemon=True)
    ws_thread.start()


if __name__ == "__main__":
    # Connect to Deepgram
    if not connect_deepgram():
        print("Could not connect to Deepgram. Exiting.")
        exit(1)
    
    # Initialize UDP receiver
    udp_receiver.start()
    
    # Start listening by default
    start_listening()
    
    # Run the WebSocket server in a separate thread
    run_websocket_server()
    
    # Run the Flask app in a separate thread
    flask_thread = threading.Thread(target=run_flask_app)
    flask_thread.daemon = True
    flask_thread.start()
    
    # Run the audio streaming handler in the main thread
    try:
        audio_stream_handler()
    except KeyboardInterrupt:
        print("Shutting down...")
        # Close the connection
        if dg_connection_context:
            dg_connection_context.__exit__(None, None, None)