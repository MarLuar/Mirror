#!/usr/bin/env python3
"""
Deepgram Speech-to-Text Server with ESP32 Audio Input
This script receives audio from ESP32 via UDP and streams it to Deepgram for real-time transcription.
"""

import asyncio
import json
import logging
import socket
import threading
import time
from datetime import datetime
from queue import Queue

import websockets
from deepgram import (
    DeepgramClient,
    LiveTranscriptionEvents,
    LiveOptions,
    Microphone,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables
dg_connection = None
udp_socket = None
audio_queue = Queue()
is_listening = False
deepgram_client = None


class UDPAudioReceiver:
    """Handles receiving audio data from ESP32 via UDP"""
    
    def __init__(self, host="0.0.0.0", port=1234):
        self.host = host
        self.port = port
        self.sock = None
        self.running = False
        
    def start(self):
        """Start the UDP receiver thread"""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.host, self.port))
        self.running = True
        
        logger.info(f"UDP Audio Receiver listening on {self.host}:{self.port}")
        
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
                    audio_queue.put(data)
            except Exception as e:
                if self.running:  # Only log if we're supposed to be running
                    logger.error(f"Error receiving UDP audio: {e}")
                    
    def stop(self):
        """Stop the UDP receiver"""
        self.running = False
        if self.sock:
            self.sock.close()


async def connect_deepgram():
    """Connect to Deepgram WebSocket API"""
    global dg_connection, deepgram_client

    # Initialize Deepgram client with the provided API key
    api_key = "961db2b8279b38dbf1fa9e1a1cdedc33b66bca1a"
    
    try:
        deepgram_client = DeepgramClient(api_key)
        
        # Define the live transcription options
        dg_options = LiveOptions(
            model="nova-2",
            language="en-US",
            # Apply smart formatting to the output
            smart_format=True,
            # To get UtteranceEnd, the following must be set:
            interim_results=True,
            utterance_end_ms="1000",
            vad_events=True,
            # Time in milliseconds of silence to wait for before finalizing speech
            endpointing=300,
        )
        
        # Create a websocket connection to Deepgram
        dg_connection = deepgram_client.listen.live.v("1")
        
        # Register callbacks
        dg_connection.on(LiveTranscriptionEvents.Transcript, handle_transcript)
        dg_connection.on(LiveTranscriptionEvents.Metadata, handle_metadata)
        dg_connection.on(LiveTranscriptionEvents.UtteranceEnd, handle_utterance_end)
        dg_connection.on(LiveTranscriptionEvents.SpeechStarted, handle_speech_started)
        dg_connection.on(LiveTranscriptionEvents.Close, handle_close)
        dg_connection.on(LiveTranscriptionEvents.Error, handle_error)
        dg_connection.on(LiveTranscriptionEvents.Unhandled, handle_unhandled)
        
        # Start the connection
        if dg_connection.start(dg_options) is False:
            logger.error("Failed to connect to Deepgram")
            return False
            
        logger.info("Connected to Deepgram WebSocket")
        return True
        
    except Exception as e:
        logger.error(f"Error connecting to Deepgram: {e}")
        return False


def handle_transcript(self, result, **kwargs):
    """Handle transcript received from Deepgram"""
    sentence = result.to_dict()["channel"]["alternatives"][0]["transcript"]
    
    if len(sentence) == 0:
        return
    
    # Check if the result contains speech_final flag
    is_final = result.to_dict()["is_final"]
    speech_final = result.to_dict()["speech_final"]
    
    if is_final or speech_final:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] SPEAKER: {sentence}\n")
    else:
        print(f"Interim: {sentence}")


def handle_metadata(self, metadata, **kwargs):
    """Handle metadata received from Deepgram"""
    logger.debug(f"Metadata: {metadata}")


def handle_utterance_end(self, utterance_end, **kwargs):
    """Handle utterance end event from Deepgram"""
    logger.debug("Utterance ended")


def handle_speech_started(self, speech_started, **kwargs):
    """Handle speech started event from Deepgram"""
    logger.debug("Speech detected")


def handle_close(self, close, **kwargs):
    """Handle close event from Deepgram"""
    logger.info("Connection closed")


def handle_error(self, error, **kwargs):
    """Handle error event from Deepgram"""
    logger.error(f"Deepgram error: {error}")


def handle_unhandled(self, unhandled, **kwargs):
    """Handle unhandled event from Deepgram"""
    logger.warning(f"Unhandled event: {unhandled}")


async def audio_stream_handler():
    """Continuously send audio data from UDP to Deepgram"""
    global is_listening
    
    while True:
        if is_listening and not audio_queue.empty() and dg_connection:
            try:
                # Get audio data from queue
                audio_data = audio_queue.get_nowait()
                
                # Send audio data to Deepgram
                dg_connection.send(audio_data)
                
            except Exception as e:
                # Queue is empty, continue
                await asyncio.sleep(0.01)
                continue
        else:
            # Small delay to prevent busy-waiting
            await asyncio.sleep(0.01)


def start_listening():
    """Start the listening process"""
    global is_listening
    if not is_listening:
        is_listening = True
        logger.info("Started listening for audio...")


def stop_listening():
    """Stop the listening process"""
    global is_listening
    if is_listening:
        is_listening = False
        logger.info("Stopped listening for audio")


async def main():
    """Main function to run the STT server"""
    global dg_connection, udp_socket
    
    # Initialize UDP receiver
    udp_receiver = UDPAudioReceiver()
    udp_receiver.start()
    
    # Connect to Deepgram
    if not await connect_deepgram():
        logger.error("Could not connect to Deepgram. Exiting.")
        return
    
    try:
        # Start listening by default
        start_listening()
        
        # Run the audio streaming handler
        await audio_stream_handler()
        
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        stop_listening()
        if dg_connection:
            dg_connection.finish()
        udp_receiver.stop()


if __name__ == "__main__":
    # Run the main function
    asyncio.run(main())