#!/usr/bin/env python3
"""
Microphone Test for Deepgram STT
This script captures audio from your laptop's microphone and sends it to Deepgram for real-time transcription.
"""

import asyncio
import json
import logging
import pyaudio
import threading
import time
from datetime import datetime

from deepgram import (
    DeepgramClient,
    ListenWSOptions,
    LiveTranscriptionEvents,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables
dg_connection = None
deepgram_client = None
audio_stream = None
p = None


class MicrophoneTest:
    """Handles capturing audio from laptop microphone and sending to Deepgram"""

    def __init__(self):
        self.api_key = "961db2b8279b38dbf1fa9e1a1cdedc33b66bca1a"
        self.is_listening = False

    async def connect_deepgram(self):
        """Connect to Deepgram WebSocket API"""
        global dg_connection, deepgram_client

        try:
            deepgram_client = DeepgramClient(self.api_key)

            # Define the live transcription options
            dg_options = ListenWSOptions(
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
            dg_connection = deepgram_client.listen.websocket.v("1")

            # Register callbacks
            dg_connection.on(LiveTranscriptionEvents.Transcript, self.handle_transcript)
            dg_connection.on(LiveTranscriptionEvents.Metadata, self.handle_metadata)
            dg_connection.on(LiveTranscriptionEvents.UtteranceEnd, self.handle_utterance_end)
            dg_connection.on(LiveTranscriptionEvents.SpeechStarted, self.handle_speech_started)
            dg_connection.on(LiveTranscriptionEvents.Close, self.handle_close)
            dg_connection.on(LiveTranscriptionEvents.Error, self.handle_error)
            dg_connection.on(LiveTranscriptionEvents.Unhandled, self.handle_unhandled)

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
            print(f"\n[{timestamp}] SPEAKER: {sentence}\n")
        else:
            # Print interim results on same line to avoid clutter
            print(f"\rInterim: {sentence}", end="", flush=True)

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

    def start_microphone_capture(self):
        """Start capturing audio from microphone and sending to Deepgram"""
        global audio_stream, p
        
        # Initialize PyAudio
        p = pyaudio.PyAudio()

        # Open audio stream
        audio_stream = p.open(
            format=pyaudio.paInt16,  # 16-bit resolution
            channels=1,              # Mono
            rate=16000,              # 16kHz sampling rate
            input=True,              # Input stream
            frames_per_buffer=1024   # Buffer size
        )
        
        logger.info("Microphone initialized. Starting audio capture...")
        print("Speak now! Transcriptions will appear below:")
        print("-" * 50)

        self.is_listening = True

        # Continuously read audio and send to Deepgram
        while self.is_listening:
            try:
                # Read raw audio data from the microphone
                audio_data = audio_stream.read(1024, exception_on_overflow=False)
                
                # Send audio data to Deepgram
                if dg_connection:
                    dg_connection.send(audio_data)
                    
            except Exception as e:
                logger.error(f"Error reading audio: {e}")
                break

    def stop_microphone_capture(self):
        """Stop microphone capture"""
        self.is_listening = False
        if audio_stream:
            audio_stream.stop_stream()
            audio_stream.close()
        if p:
            p.terminate()
        logger.info("Microphone capture stopped")

    async def run_test(self):
        """Run the microphone test"""
        # Connect to Deepgram
        if not await self.connect_deepgram():
            logger.error("Could not connect to Deepgram. Exiting.")
            return

        try:
            # Start microphone capture in a separate thread to avoid blocking
            mic_thread = threading.Thread(target=self.start_microphone_capture)
            mic_thread.daemon = True
            mic_thread.start()

            # Keep the main thread alive
            while self.is_listening:
                await asyncio.sleep(0.1)

        except KeyboardInterrupt:
            logger.info("Stopping microphone test...")
        finally:
            self.stop_microphone_capture()
            if dg_connection:
                dg_connection.finish()


async def main():
    """Main function to run the microphone test"""
    test = MicrophoneTest()
    await test.run_test()


if __name__ == "__main__":
    # Run the main function
    asyncio.run(main())