#!/usr/bin/env python3
"""
Integrated Speech Analysis System with ESP32 Wireless Microphone Support
This script combines the existing speech analysis features with ESP32 audio input via UDP.
"""

import os
import json
import asyncio
import socket
import threading
import time
from datetime import datetime
from queue import Queue
from dotenv import load_dotenv
from api.deepgram_client import DeepgramClientWrapper
from audio.microphone import MicrophoneHandler
from analysis.speech_analyzer import SpeechAnalyzer
from utils.logger import setup_logger
from utils.prompter import TextPrompter
from utils.recording_manager import RecordingManager
from utils.oled_display import OLEDDisplay

# Load environment variables
load_dotenv()

logger = setup_logger(__name__)

# Global variables for ESP32 audio
audio_queue = Queue()
is_listening = False
esp32_dg_client = None
esp32_speech_analyzer = None
esp32_recording_manager = None


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
        packet_count = 0
        while self.running:
            try:
                data, addr = self.sock.recvfrom(4096)
                if is_listening:
                    # Put audio data in queue for processing
                    audio_queue.put(data)
                    
                    # Print status every 100 packets
                    packet_count += 1
                    if packet_count % 100 == 0:
                        print(f"[ESP32] Received {packet_count} packets from {addr}")
                        
            except Exception as e:
                if self.running:  # Only log if we're supposed to be running
                    logger.error(f"Error receiving UDP audio: {e}")

    def stop(self):
        """Stop the UDP receiver"""
        self.running = False
        if self.sock:
            self.sock.close()


class IntegratedSpeechAnalysisApp:
    def __init__(self, config_path="config.json"):
        """
        Initialize the integrated speech analysis application
        """
        # Load configuration
        with open(config_path, 'r') as f:
            self.config = json.load(f)

        # Initialize components for regular microphone
        self.dg_client = DeepgramClientWrapper(os.getenv('DEEPGRAM_API_KEY'))
        self.mic_handler = MicrophoneHandler()
        self.speech_analyzer = SpeechAnalyzer()
        self.prompter = TextPrompter()
        self.recording_manager = RecordingManager()

        # Initialize components for ESP32
        global esp32_dg_client, esp32_speech_analyzer, esp32_recording_manager
        esp32_dg_client = DeepgramClientWrapper(os.getenv('DEEPGRAM_API_KEY'))
        esp32_speech_analyzer = SpeechAnalyzer()
        esp32_recording_manager = RecordingManager()

        # Initialize UDP receiver with configurable port
        audio_port = self.config.get("esp32", {}).get("audio_port", 1234)
        self.udp_receiver = UDPAudioReceiver(port=audio_port)

        # Initialize UDP socket for sending prompts to ESP32
        try:
            self.prompt_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # Get ESP32 configuration from config file
            self.esp32_ip = self.config.get("esp32", {}).get("ip_address", "10.42.0.156")
            self.prompt_port = self.config.get("esp32", {}).get("prompt_port", 1235)
            self.playback_port = self.config.get("esp32", {}).get("playback_port", 1236)
            print(f"Initialized prompt sending to ESP32 at {self.esp32_ip}:{self.prompt_port}")
            print(f"Initialized playback sending to ESP32 at {self.esp32_ip}:{self.playback_port}")
        except Exception as e:
            print(f"Could not initialize ESP32 prompt sending: {e}")
            self.prompt_socket = None

        # Initialize OLED display (optional - won't fail if hardware not present)
        try:
            self.oled_display = OLEDDisplay()
            self.oled_available = True
            self.oled_display.display_startup_message()
        except Exception as e:
            print(f"OLED display not available: {e}")
            self.oled_available = False

        # Audio buffer to accumulate data for ESP32 transcription
        self.esp32_audio_buffer = b""
        self.sample_rate = 44100  # From ESP32 config
        self.channels = 2  # From ESP32 config
        self.sample_width = 2  # 16-bit from ESP32 config

    def start_esp32_listening(self):
        """Start the ESP32 listening process"""
        global is_listening
        if not is_listening:
            is_listening = True
            logger.info("Started listening for audio from ESP32...")
            print("Started listening for audio from ESP32...")

    def stop_esp32_listening(self):
        """Stop the ESP32 listening process"""
        global is_listening
        if is_listening:
            is_listening = False
            logger.info("Stopped listening for audio from ESP32...")
            print("Stopped listening for audio from ESP32...")

    async def run_esp32_analysis(self, duration=10):
        """
        Run speech analysis using ESP32 audio input
        :param duration: Recording duration in seconds
        """
        global is_listening

        print(f"Collecting audio from ESP32 for {duration} seconds...")
        start_time = time.time()

        # Clear any existing audio in the queue
        while not audio_queue.empty():
            audio_queue.get()

        # Start listening
        self.start_esp32_listening()

        # Reset audio buffer
        self.esp32_audio_buffer = b""

        # Calculate maximum buffer size to avoid timeouts (based on sample rate, channels, and sample width)
        # For custom duration option, use the specified duration but with timeout handling
        # Note: ESP32 sends stereo audio at 44.1kHz, so we need to account for that
        max_buffer_size = int(self.sample_rate * self.channels * self.sample_width * duration)

        # Add a small buffer to account for timing variations
        max_buffer_size = int(max_buffer_size * 1.1)  # 10% extra to account for timing variations

        # Collect audio for the specified duration
        while time.time() - start_time < duration:
            if not audio_queue.empty():
                audio_chunk = audio_queue.get()

                # Check if adding this chunk would exceed the max buffer size
                if len(self.esp32_audio_buffer) + len(audio_chunk) <= max_buffer_size:
                    self.esp32_audio_buffer += audio_chunk
                else:
                    # Truncate the chunk to fit in the remaining space
                    remaining_space = max_buffer_size - len(self.esp32_audio_buffer)
                    if remaining_space > 0:
                        self.esp32_audio_buffer += audio_chunk[:remaining_space]

                # Calculate approximate time based on data size
                elapsed_time = len(self.esp32_audio_buffer) / (self.channels * self.sample_width * self.sample_rate)

                # Only print status every 10 seconds to reduce log spam
                if int(elapsed_time) % 10 == 0 and elapsed_time > 0:
                    print(f"[ESP32] Collected {elapsed_time:.1f}s of audio...")

            await asyncio.sleep(0.01)  # Small delay to prevent busy waiting

        # Stop listening
        self.stop_esp32_listening()

        print(f"[ESP32] Collected approximately {len(self.esp32_audio_buffer) / (self.channels * self.sample_width * self.sample_rate):.2f} seconds of audio")

        if len(self.esp32_audio_buffer) == 0:
            print("[ESP32] No audio data collected from ESP32")
            return None, None

        # Send processing message to ESP32
        self.send_processing_to_esp32()

        # Transcribe the collected audio
        try:
            print("[ESP32] Transcribing audio...")
            transcription = await esp32_dg_client.transcribe_audio_from_bytes_with_retry(
                self.esp32_audio_buffer,
                sample_rate=self.sample_rate,
                channels=self.channels,
                sample_width=self.sample_width
            )

            print(f"[ESP32] Transcription: {transcription}")

            # Analyze speech aspects
            logger.info("[ESP32] Analyzing speech...")
            analysis_results = esp32_speech_analyzer.analyze_speech(transcription, None)

            # Calculate average score for display
            numeric_scores = [score for score in analysis_results.values() if isinstance(score, (int, float))]
            avg_score = sum(numeric_scores) / len(numeric_scores) if numeric_scores else 0

            # Send results to ESP32
            self.send_results_to_esp32(transcription, analysis_results, avg_score)

            # Save the recording with analysis results FIRST (for playback)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            recording_filename = f"esp32_wireless_mic_{timestamp}"
            audio_params = {
                'channels': self.channels,
                'sample_width': self.sample_width,
                'framerate': self.sample_rate
            }
            recording_path = esp32_recording_manager.save_recording(
                self.esp32_audio_buffer,
                recording_filename,
                audio_params,
                analysis_results,
                transcription
            )
            print(f"[ESP32] Recording saved as: {os.path.basename(recording_path)}")

            # Wait briefly for ESP32 to display results, then send improvement suggestions
            time.sleep(5)  # Wait for ESP32 to show scores

            # Generate and send improvement suggestions to ESP32
            improvement_tips = self.generate_improvement_suggestions(analysis_results)
            if improvement_tips:
                # Send improvement suggestions to ESP32 after showing scores
                self.send_improvement_to_esp32(improvement_tips)
                # Send playback of the recording to ESP32 speaker
                # ESP32 will switch to playback mode 5 seconds after receiving IMPROVE:
                self.send_playback_to_esp32(recording_path, delay_before_playback=6.0)

            # Display results
            self.display_results(transcription, analysis_results, source="ESP32 Wireless Mic")

            return transcription, analysis_results

        except Exception as e:
            logger.error(f"[ESP32] Error processing audio: {str(e)}")
            print(f"[ESP32] Error processing audio: {str(e)}")

            # Try to handle the timeout by reducing the audio buffer
            if "timeout" in str(e).lower():
                print("[ESP32] Attempting to retry with reduced audio buffer...")
                # Reduce the buffer to half and try again
                reduced_buffer = self.esp32_audio_buffer[:len(self.esp32_audio_buffer)//2]
                try:
                    print("[ESP32] Retrying transcription with reduced buffer...")
                    transcription = await esp32_dg_client.transcribe_audio_from_bytes_with_retry(
                        reduced_buffer,
                        sample_rate=self.sample_rate,
                        channels=self.channels,
                        sample_width=self.sample_width
                    )

                    print(f"[ESP32] Transcription: {transcription}")

                    # Analyze speech aspects
                    logger.info("[ESP32] Analyzing speech...")
                    analysis_results = esp32_speech_analyzer.analyze_speech(transcription, None)

                    # Calculate average score for display
                    numeric_scores = [score for score in analysis_results.values() if isinstance(score, (int, float))]
                    avg_score = sum(numeric_scores) / len(numeric_scores) if numeric_scores else 0

                    # Send results to ESP32
                    self.send_results_to_esp32(transcription, analysis_results, avg_score)

                    # Save the recording with analysis results FIRST
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    recording_filename = f"esp32_wireless_mic_reduced_{timestamp}"
                    audio_params = {
                        'channels': self.channels,
                        'sample_width': self.sample_width,
                        'framerate': self.sample_rate
                    }
                    recording_path = esp32_recording_manager.save_recording(
                        reduced_buffer,
                        recording_filename,
                        audio_params,
                        analysis_results,
                        transcription
                    )
                    print(f"[ESP32] Recording saved as: {os.path.basename(recording_path)}")

                    # Wait briefly for ESP32 to display results, then send improvement suggestions
                    time.sleep(5)  # Wait for ESP32 to show scores

                    # Generate and send improvement suggestions to ESP32
                    improvement_tips = self.generate_improvement_suggestions(analysis_results)
                    if improvement_tips:
                        # Send improvement suggestions to ESP32 after showing scores
                        self.send_improvement_to_esp32(improvement_tips)
                        # Send playback of the recording to ESP32 speaker
                        self.send_playback_to_esp32(recording_path, delay_before_playback=6.0)

                    # Display results
                    self.display_results(transcription, analysis_results, source="ESP32 Wireless Mic (Reduced)")

                    return transcription, analysis_results
                except Exception as retry_e:
                    logger.error(f"[ESP32] Retry also failed: {str(retry_e)}")
                    print(f"[ESP32] Retry also failed: {str(retry_e)}")

            return None, None

    def send_prompt_to_esp32(self, prompt_text):
        """
        Send the prompt text to the ESP32 for display on its OLED
        :param prompt_text: The prompt text to send
        """
        if self.prompt_socket:
            try:
                # Send the prompt text to the ESP32 via UDP
                self.prompt_socket.sendto(prompt_text.encode('utf-8'), (self.esp32_ip, self.prompt_port))
                print(f"Sent prompt to ESP32: {prompt_text[:50]}{'...' if len(prompt_text) > 50 else ''}")
            except Exception as e:
                print(f"Failed to send prompt to ESP32: {e}")

    def send_processing_to_esp32(self):
        """
        Send a processing message to the ESP32 to clear the prompt and show processing status
        """
        if self.prompt_socket:
            try:
                # Send a special processing message to the ESP32
                processing_msg = "PROCESSING_AUDIO"
                self.prompt_socket.sendto(processing_msg.encode('utf-8'), (self.esp32_ip, self.prompt_port))
                print("Sent processing message to ESP32")
            except Exception as e:
                print(f"Failed to send processing message to ESP32: {e}")

    def send_results_to_esp32(self, transcription, analysis_results, avg_score):
        """
        Send results to the ESP32 to display on its OLED
        :param transcription: The transcribed text
        :param analysis_results: Dictionary with detailed analysis results
        :param avg_score: Average score to display
        """
        if self.prompt_socket:
            try:
                # Create a detailed results string with key metrics
                # Extract key scores for display on the small OLED
                pronunciation = analysis_results.get('pronunciation', 0)
                articulation = analysis_results.get('articulation', 0)
                pace = analysis_results.get('pace', 0)
                clarity = analysis_results.get('clarity', 0)
                emotion = analysis_results.get('emotion', 'unknown')

                # Format detailed results string with short names to fit OLED better - include all scores
                detailed_results = f"Pr:{pronunciation:.1f} Ar:{articulation:.1f} Pa:{pace:.1f} Cl:{clarity:.1f}"

                # Send results as a formatted message to the ESP32
                results_msg = f"SCORE:{avg_score:.1f}|{detailed_results}"
                self.prompt_socket.sendto(results_msg.encode('utf-8'), (self.esp32_ip, self.prompt_port))
                print(f"Sent results to ESP32: {results_msg}")
            except Exception as e:
                print(f"Failed to send results to ESP32: {e}")

    async def run_esp32_analysis_with_prompt(self, duration=10):
        """
        Run speech analysis using ESP32 audio input with a prompt to read
        :param duration: Recording duration in seconds
        """
        global is_listening

        # Get a text prompt for the user to read
        prompt_result = self.prompter.get_prompt_with_duration_info(duration)
        prompt_text = prompt_result['text']

        # Display prompt on local OLED if available
        if self.oled_available:
            self.oled_display.display_prompt_and_ratings(prompt_text)

        # Send prompt to ESP32 for display on its OLED
        self.send_prompt_to_esp32(prompt_text)

        print(f"\nRecording for {duration} seconds. Please speak now...")
        print(f"\nReading prompt ({prompt_result['estimated_reading_time']}s):")
        print(f">>> {prompt_text}")
        print("-" * 60)

        start_time = time.time()

        # Clear any existing audio in the queue
        while not audio_queue.empty():
            audio_queue.get()

        # Start listening
        self.start_esp32_listening()

        # Reset audio buffer
        self.esp32_audio_buffer = b""

        # Calculate maximum buffer size to avoid timeouts (based on sample rate, channels, and sample width)
        max_buffer_size = int(self.sample_rate * self.channels * self.sample_width * duration)

        # Add a small buffer to account for timing variations
        max_buffer_size = int(max_buffer_size * 1.1)  # 10% extra to account for timing variations

        # Collect audio for the specified duration
        while time.time() - start_time < duration:
            if not audio_queue.empty():
                audio_chunk = audio_queue.get()

                # Check if adding this chunk would exceed the max buffer size
                if len(self.esp32_audio_buffer) + len(audio_chunk) <= max_buffer_size:
                    self.esp32_audio_buffer += audio_chunk
                else:
                    # Truncate the chunk to fit in the remaining space
                    remaining_space = max_buffer_size - len(self.esp32_audio_buffer)
                    if remaining_space > 0:
                        self.esp32_audio_buffer += audio_chunk[:remaining_space]

                # Calculate approximate time based on data size
                elapsed_time = len(self.esp32_audio_buffer) / (self.channels * self.sample_width * self.sample_rate)

                # Only print status every 10 seconds to reduce log spam
                if int(elapsed_time) % 10 == 0 and elapsed_time > 0:
                    print(f"[ESP32] Collected {elapsed_time:.1f}s of audio...")

            await asyncio.sleep(0.01)  # Small delay to prevent busy waiting

        # Stop listening
        self.stop_esp32_listening()

        print(f"[ESP32] Collected approximately {len(self.esp32_audio_buffer) / (self.channels * self.sample_width * self.sample_rate):.2f} seconds of audio")

        if len(self.esp32_audio_buffer) == 0:
            print("[ESP32] No audio data collected from ESP32")
            return None, None

        # Send processing message to ESP32
        self.send_processing_to_esp32()

        # Transcribe the collected audio
        try:
            print("[ESP32] Transcribing audio...")
            transcription = await esp32_dg_client.transcribe_audio_from_bytes_with_retry(
                self.esp32_audio_buffer,
                sample_rate=self.sample_rate,
                channels=self.channels,
                sample_width=self.sample_width
            )

            print(f"[ESP32] Transcription: {transcription}")

            # Analyze speech aspects using the original prompt for comparison
            logger.info("[ESP32] Analyzing speech...")
            analysis_results = esp32_speech_analyzer.analyze_speech(transcription, prompt_text)

            # Calculate average score for display
            numeric_scores = [score for score in analysis_results.values() if isinstance(score, (int, float))]
            avg_score = sum(numeric_scores) / len(numeric_scores) if numeric_scores else 0

            # Send results to ESP32
            self.send_results_to_esp32(transcription, analysis_results, avg_score)

            # Save the recording with analysis results FIRST
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            recording_filename = f"esp32_prompted_speech_{timestamp}"
            audio_params = {
                'channels': self.channels,
                'sample_width': self.sample_width,
                'framerate': self.sample_rate
            }
            recording_path = esp32_recording_manager.save_recording(
                self.esp32_audio_buffer,
                recording_filename,
                audio_params,
                analysis_results,
                transcription
            )
            print(f"[ESP32] Recording saved as: {os.path.basename(recording_path)}")

            # Wait briefly for ESP32 to display results, then send improvement suggestions
            time.sleep(5)  # Wait for ESP32 to show scores

            # Generate and send improvement suggestions to ESP32
            improvement_tips = self.generate_improvement_suggestions(analysis_results)
            if improvement_tips:
                # Send improvement suggestions to ESP32 after showing scores
                self.send_improvement_to_esp32(improvement_tips)
                # Send playback of the recording to ESP32 speaker
                self.send_playback_to_esp32(recording_path, delay_before_playback=6.0)

            # Display results
            self.display_results(transcription, analysis_results, source="ESP32 Wireless Mic with Prompt")

            return transcription, analysis_results

        except Exception as e:
            logger.error(f"[ESP32] Error processing audio: {str(e)}")
            print(f"[ESP32] Error processing audio: {str(e)}")

            # Try to handle the timeout by reducing the audio buffer
            if "timeout" in str(e).lower():
                print("[ESP32] Attempting to retry with reduced audio buffer...")
                # Reduce the buffer to half and try again
                reduced_buffer = self.esp32_audio_buffer[:len(self.esp32_audio_buffer)//2]
                try:
                    print("[ESP32] Retrying transcription with reduced buffer...")
                    transcription = await esp32_dg_client.transcribe_audio_from_bytes_with_retry(
                        reduced_buffer,
                        sample_rate=self.sample_rate,
                        channels=self.channels,
                        sample_width=self.sample_width
                    )

                    print(f"[ESP32] Transcription: {transcription}")

                    # Analyze speech aspects using the original prompt for comparison
                    logger.info("[ESP32] Analyzing speech...")
                    analysis_results = esp32_speech_analyzer.analyze_speech(transcription, prompt_text)

                    # Calculate average score for display
                    numeric_scores = [score for score in analysis_results.values() if isinstance(score, (int, float))]
                    avg_score = sum(numeric_scores) / len(numeric_scores) if numeric_scores else 0

                    # Send results to ESP32
                    self.send_results_to_esp32(transcription, analysis_results, avg_score)

                    # Save the recording with analysis results FIRST
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    recording_filename = f"esp32_prompted_speech_reduced_{timestamp}"
                    audio_params = {
                        'channels': self.channels,
                        'sample_width': self.sample_width,
                        'framerate': self.sample_rate
                    }
                    recording_path = esp32_recording_manager.save_recording(
                        reduced_buffer,
                        recording_filename,
                        audio_params,
                        analysis_results,
                        transcription
                    )
                    print(f"[ESP32] Recording saved as: {os.path.basename(recording_path)}")

                    # Wait briefly for ESP32 to display results, then send improvement suggestions
                    time.sleep(5)  # Wait for ESP32 to show scores

                    # Generate and send improvement suggestions to ESP32
                    improvement_tips = self.generate_improvement_suggestions(analysis_results)
                    if improvement_tips:
                        # Send improvement suggestions to ESP32 after showing scores
                        self.send_improvement_to_esp32(improvement_tips)
                        # Send playback of the recording to ESP32 speaker
                        self.send_playback_to_esp32(recording_path, delay_before_playback=6.0)

                    # Display results
                    self.display_results(transcription, analysis_results, source="ESP32 Wireless Mic with Prompt (Reduced)")

                    return transcription, analysis_results
                except Exception as retry_e:
                    logger.error(f"[ESP32] Retry also failed: {str(retry_e)}")
                    print(f"[ESP32] Retry also failed: {str(retry_e)}")

            return None, None

    async def run_analysis(self, duration=None):
        """
        Run a complete speech analysis cycle using regular microphone
        :param duration: Recording duration in seconds (uses config default if None)
        """
        if duration is None:
            duration = self.config['recording']['duration']

        # Initialize variables to avoid UnboundLocalError
        analysis_results = None
        transcription = None

        try:
            # Get a text prompt for the user to read
            prompt_result = self.prompter.get_prompt_with_duration_info(duration)
            prompt_text = prompt_result['text']

            # Display prompt on local OLED if available
            if self.oled_available:
                self.oled_display.display_prompt_and_ratings(prompt_text)

            # Send prompt to ESP32 for display on its OLED
            self.send_prompt_to_esp32(prompt_text)

            # Record audio from microphone
            logger.info(f"Recording audio for {duration} seconds...")
            print(f"\nRecording for {duration} seconds. Please speak now...")
            print(f"\nReading prompt ({prompt_result['estimated_reading_time']}s):")
            print(f">>> {prompt_text}")
            print("-" * 60)

            audio_data = await self.mic_handler.record_audio(duration=duration)
            print("Recording completed.\n")

            # Transcribe audio using Deepgram
            logger.info("Transcribing audio...")
            print("Processing your speech...")
            transcription = await self.dg_client.transcribe_audio(audio_data)

            # Analyze speech aspects
            logger.info("Analyzing speech...")
            analysis_results = self.speech_analyzer.analyze_speech(transcription, prompt_text)

            # Display results
            self.display_results(transcription, analysis_results, source="Microphone")

            # Ask if user wants to save this recording
            save_choice = input("\nWould you like to save this recording and analysis? (y/n): ").strip().lower()
            if save_choice == 'y' or save_choice == 'yes':
                # Save the recording with analysis results
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                recording_filename = f"prompted_speech_not_saved_{timestamp}"
                audio_params = {
                    'channels': self.mic_handler.channels,
                    'sample_width': self.mic_handler.audio.get_sample_size(self.mic_handler.sample_format),
                    'framerate': self.mic_handler.fs
                }
                recording_path = self.recording_manager.save_recording(
                    audio_data,
                    recording_filename,
                    audio_params,
                    analysis_results,
                    transcription
                )
                print(f"Recording saved as: {os.path.basename(recording_path)}")

            return transcription, analysis_results

        except Exception as e:
            logger.error(f"An error occurred: {str(e)}")
            print(f"An error occurred: {str(e)}")
            return None, None

    async def run_analysis_with_save(self, duration=None):
        """
        Run a complete speech analysis cycle with prompt and save the recording
        :param duration: Recording duration in seconds (uses config default if None)
        """
        if duration is None:
            duration = self.config['recording']['duration']

        try:
            # Get a text prompt for the user to read
            prompt_result = self.prompter.get_prompt_with_duration_info(duration)
            prompt_text = prompt_result['text']

            # Display prompt on local OLED if available
            if self.oled_available:
                self.oled_display.display_prompt_and_ratings(prompt_text)

            # Send prompt to ESP32 for display on its OLED
            self.send_prompt_to_esp32(prompt_text)

            # Record audio from microphone
            logger.info(f"Recording audio for {duration} seconds...")
            print(f"\nRecording for {duration} seconds. Please speak now...")
            print(f"\nReading prompt ({prompt_result['estimated_reading_time']}s):")
            print(f">>> {prompt_text}")
            print("-" * 60)

            audio_data = await self.mic_handler.record_audio(duration=duration)
            print("Recording completed.\n")

            # Transcribe audio using Deepgram
            logger.info("Transcribing audio...")
            print("Processing your speech...")
            transcription = await self.dg_client.transcribe_audio(audio_data)

            # Analyze speech aspects
            logger.info("Analyzing speech...")
            analysis_results = self.speech_analyzer.analyze_speech(transcription, prompt_text)

            # Save the recording with analysis results
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            recording_filename = f"prompted_speech_{timestamp}"
            audio_params = {
                'channels': self.mic_handler.channels,
                'sample_width': self.mic_handler.audio.get_sample_size(self.mic_handler.sample_format),
                'framerate': self.mic_handler.fs
            }
            recording_path = self.recording_manager.save_recording(
                audio_data,
                recording_filename,
                audio_params,
                analysis_results,
                transcription
            )
            print(f"Recording saved as: {os.path.basename(recording_path)}")

            # Display results
            self.display_results(transcription, analysis_results, source="Microphone")

            return transcription, analysis_results

        except Exception as e:
            logger.error(f"An error occurred: {str(e)}")
            print(f"An error occurred: {str(e)}")
            return None, None

    async def run_free_analysis(self, duration=None):
        """
        Run a complete speech analysis cycle without a prompt
        :param duration: Recording duration in seconds (uses config default if None)
        """
        if duration is None:
            duration = self.config['recording']['duration']

        try:
            # Record audio from microphone
            logger.info(f"Recording audio for {duration} seconds...")
            print(f"\nRecording for {duration} seconds. Speak freely now...")
            audio_data = await self.mic_handler.record_audio(duration=duration)
            print("Recording completed.\n")

            # Transcribe audio using Deepgram
            logger.info("Transcribing audio...")
            print("Processing your speech...")
            transcription = await self.dg_client.transcribe_audio(audio_data)

            # Analyze speech aspects (no original prompt for free speech)
            logger.info("Analyzing speech...")
            analysis_results = self.speech_analyzer.analyze_speech(transcription, None)

            # Save the recording with analysis results
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            recording_filename = f"free_speech_{timestamp}"
            audio_params = {
                'channels': self.mic_handler.channels,
                'sample_width': self.mic_handler.audio.get_sample_size(self.mic_handler.sample_format),
                'framerate': self.mic_handler.fs
            }
            recording_path = self.recording_manager.save_recording(
                audio_data,
                recording_filename,
                audio_params,
                analysis_results,
                transcription
            )
            print(f"Recording saved as: {os.path.basename(recording_path)}")

            # Display results
            self.display_results(transcription, analysis_results, source="Microphone")

            return transcription, analysis_results

        except Exception as e:
            logger.error(f"An error occurred: {str(e)}")
            print(f"An error occurred: {str(e)}")
            return None, None

    def display_results(self, transcription, analysis_results, source="Microphone"):
        """
        Display the analysis results in a formatted way
        """
        print("="*60)
        print(f"SPEECH ANALYSIS RESULTS - {source.upper()}")
        print("="*60)
        print(f"Transcription: {transcription}")
        print("\nDetailed Scores:")

        # Define descriptions for each aspect
        descriptions = {
            'pronunciation': 'Estimated quality based on transcription accuracy',
            'articulation': 'Clarity of individual word formation',
            'pace': 'Consistency and appropriateness of speaking speed',
            'clarity': 'How clear and understandable your speech was',
            'emotion': 'Emotional tone of your speech'
        }

        for aspect, score in analysis_results.items():
            description = descriptions.get(aspect, 'Aspect evaluation')
            if isinstance(score, str):
                # Handle string values like emotion
                print(f"  {aspect.capitalize():<12}: {score:<7} - {description}")
            else:
                # Handle numeric scores
                print(f"  {aspect.capitalize():<12}: {score:>4.1f}/10 - {description}")

        print("\nOverall Assessment:")
        # Calculate average score excluding non-numeric values like emotion
        numeric_scores = [score for score in analysis_results.values() if isinstance(score, (int, float))]
        if numeric_scores:
            avg_score = sum(numeric_scores) / len(numeric_scores)
            if avg_score >= 8:
                level = "Excellent!"
            elif avg_score >= 6:
                level = "Good"
            elif avg_score >= 4:
                level = "Fair"
            else:
                level = "Needs improvement"

            print(f"  Average Score: {avg_score:.1f}/10 ({level})")
        else:
            print("  Average Score: Could not calculate (no numeric scores available)")
        print("="*60)

        # Display results on OLED if available
        if self.oled_available:
            # Show detailed results on OLED
            self.oled_display.display_prompt_and_ratings(
                f"Score: {sum([score for score in analysis_results.values() if isinstance(score, (int, float))]) / len([score for score in analysis_results.values() if isinstance(score, (int, float))]):.1f}/10" if [score for score in analysis_results.values() if isinstance(score, (int, float))] else "Analysis Complete",
                analysis_results
            )
            time.sleep(5)  # Show results for 5 seconds

            # NOTE: IMPROVE message is already sent in the main ESP32 flow
            # before calling display_results, so we skip it here to avoid double-sending
            if "ESP32" not in source:
                # Generate and send improvement suggestions to ESP32
                improvement_tips = self.generate_improvement_suggestions(analysis_results)
                if improvement_tips:
                    # Send improvement suggestions to ESP32 after showing scores
                    self.send_improvement_to_esp32(improvement_tips)
                    time.sleep(7)  # Show improvement tips for 7 seconds

    def generate_improvement_suggestions(self, analysis_results):
        """
        Generate improvement suggestions based on analysis results
        :param analysis_results: Dictionary with analysis results
        :return: Improvement suggestions string
        """
        suggestions = []

        # Check pronunciation score
        if 'pronunciation' in analysis_results and analysis_results['pronunciation'] < 6:
            suggestions.append("Practice pronunciation")

        # Check articulation score
        if 'articulation' in analysis_results and analysis_results['articulation'] < 6:
            suggestions.append("Focus on clearer words")

        # Check pace score
        if 'pace' in analysis_results and analysis_results['pace'] < 6:
            suggestions.append("Work on speaking speed")

        # Check clarity score
        if 'clarity' in analysis_results and analysis_results['clarity'] < 6:
            suggestions.append("Speak louder/clearer")

        # Check emotion score
        if 'emotion' in analysis_results and isinstance(analysis_results['emotion'], str):
            emotion = analysis_results['emotion'].lower()
            if emotion == 'negative':
                suggestions.append("Use more positive tone")
            elif emotion == 'neutral':
                suggestions.append("Add more expression")

        # Combine suggestions
        if suggestions:
            return " ".join(suggestions)
        else:
            return "Great job! Keep practicing to maintain your skills."

    def send_improvement_to_esp32(self, improvement_tips):
        """
        Send improvement suggestions to the ESP32 to display on its OLED
        :param improvement_tips: Improvement suggestions to display
        """
        if self.prompt_socket:
            try:
                # Send improvement tips to the ESP32 via UDP
                improvement_msg = f"IMPROVE:{improvement_tips}"
                self.prompt_socket.sendto(improvement_msg.encode('utf-8'), (self.esp32_ip, self.prompt_port))
                print(f"Sent improvement tips to ESP32: {improvement_tips[:50]}{'...' if len(improvement_tips) > 50 else ''}")
            except Exception as e:
                print(f"Failed to send improvement tips to ESP32: {e}")

    def send_playback_to_esp32(self, recording_path, delay_before_playback=2.0):
        """
        Send recorded audio back to ESP32 for playback through speaker
        :param recording_path: Path to the WAV file to play back
        :param delay_before_playback: Delay in seconds to allow ESP32 to switch modes
        """
        import wave
        
        if not os.path.exists(recording_path):
            print(f"Playback file not found: {recording_path}")
            return
        
        try:
            with wave.open(recording_path, 'rb') as wav:
                channels = wav.getnchannels()
                sample_width = wav.getsampwidth()
                frame_rate = wav.getframerate()
                n_frames = wav.getnframes()
                duration = n_frames / frame_rate
                
                print(f"\nLoading playback audio: {recording_path}")
                print(f"  Duration: {duration:.2f}s, Channels: {channels}, Rate: {frame_rate}Hz")
                
                # Read audio data
                audio_data = wav.readframes(n_frames)
                print(f"  Loaded {len(audio_data)} bytes")
        except Exception as e:
            print(f"Error reading playback file: {e}")
            return
        
        # Create UDP socket for playback
        try:
            playback_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            playback_socket.settimeout(5.0)
            
            print(f"\nWaiting {delay_before_playback}s for ESP32 to switch to playback mode...")
            time.sleep(delay_before_playback)
            
            # Send START command
            print("Sending START command to ESP32...")
            playback_socket.sendto(b"START", (self.esp32_ip, self.playback_port))
            time.sleep(0.2)
            
            # Send audio data in chunks
            chunk_size = 1024
            total_sent = 0
            packet_count = 0
            
            print(f"Sending {len(audio_data)} bytes in {chunk_size}-byte chunks...")
            start_time = time.time()
            
            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i:i+chunk_size]
                playback_socket.sendto(chunk, (self.esp32_ip, self.playback_port))
                total_sent += len(chunk)
                packet_count += 1
                
                if packet_count % 100 == 0:
                    progress = (total_sent / len(audio_data)) * 100
                    print(f"  Progress: {progress:.1f}% ({packet_count} packets)")
                
                # Small delay to match playback rate
                time.sleep(0.004)
            
            transfer_time = time.time() - start_time
            print(f"✅ Playback sent! {packet_count} packets in {transfer_time:.2f}s")
            
            # Send END signal
            for _ in range(5):
                playback_socket.sendto(b"END", (self.esp32_ip, self.playback_port))
                time.sleep(0.05)
            
            playback_socket.close()
            print("Playback complete - ESP32 should now be playing your speech")
            print("\n⚠️  ESP32 will restart after playback...")
            print("Waiting 12 seconds for ESP32 to restart and stabilize...")
            time.sleep(12)
            
            # Clear any pending/old UDP packets from previous session
            print("Clearing old UDP packets...")
            try:
                clear_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                clear_socket.bind(("0.0.0.0", self.prompt_port))
                clear_socket.settimeout(0.1)
                cleared = 0
                while True:
                    try:
                        clear_socket.recv(1024)
                        cleared += 1
                    except socket.timeout:
                        break
                clear_socket.close()
                if cleared > 0:
                    print(f"Cleared {cleared} old packets")
            except:
                pass
            
            print("ESP32 should be ready now.\n")
            
        except Exception as e:
            print(f"Error sending playback to ESP32: {e}")

    async def playback_recording(self):
        """
        Allow user to select and play back a recording
        """
        import json
        import os

        try:
            recordings = self.recording_manager.list_recordings()

            if not recordings:
                print("No recordings found.")
                return

            print(f"\nAvailable recordings ({len(recordings)} found):")
            for i, recording_path in enumerate(recordings, 1):
                info = self.recording_manager.get_recording_info(recording_path)

                # Check if there's an associated analysis file
                json_path = recording_path.replace('.wav', '.json')
                analysis_info = ""
                if os.path.exists(json_path):
                    try:
                        with open(json_path, 'r') as f:
                            data = json.load(f)
                        avg_score = sum(data['analysis_results'].values()) / len(data['analysis_results'])
                        analysis_info = f" - Score: {avg_score:.1f}/10"
                    except:
                        analysis_info = " - (analysis file exists)"

                print(f"{i}. {info['filename']} - {info['modified']} - {info['size']/1024:.1f}KB{analysis_info}")

            while True:
                try:
                    choice = input(f"\nSelect a recording to play (1-{len(recordings)}) or 'q' to quit: ").strip()

                    if choice.lower() == 'q':
                        break

                    index = int(choice) - 1
                    if 0 <= index < len(recordings):
                        selected_path = recordings[index]
                        info = self.recording_manager.get_recording_info(selected_path)

                        print(f"\nPlaying: {info['filename']}")

                        # Show analysis results if available
                        json_path = selected_path.replace('.wav', '.json')
                        if os.path.exists(json_path):
                            try:
                                with open(json_path, 'r') as f:
                                    data = json.load(f)

                                print("\nAnalysis Results:")
                                print(f"Transcription: {data['transcription']}")
                                print("\nDetailed Scores:")

                                # Define descriptions for each aspect
                                descriptions = {
                                    'pronunciation': 'Estimated quality based on transcription accuracy',
                                    'articulation': 'Clarity of individual word formation',
                                    'pace': 'Consistency and appropriateness of speaking speed',
                                    'clarity': 'How clear and understandable your speech was',
                                    'emotion': 'Emotional tone of your speech'
                                }

                                for aspect, score in data['analysis_results'].items():
                                    description = descriptions.get(aspect, 'Aspect evaluation')
                                    if isinstance(score, str):
                                        # Handle string values like emotion
                                        print(f"  {aspect.capitalize():<12}: {score:<7} - {description}")
                                    else:
                                        # Handle numeric scores
                                        print(f"  {aspect.capitalize():<12}: {score:>4.1f}/10 - {description}")

                                # Calculate average score excluding non-numeric values like emotion
                                numeric_scores = [score for score in data['analysis_results'].values() if isinstance(score, (int, float))]
                                if numeric_scores:
                                    avg_score = sum(numeric_scores) / len(numeric_scores)
                                    if avg_score >= 8:
                                        level = "Excellent!"
                                    elif avg_score >= 6:
                                        level = "Good"
                                    elif avg_score >= 4:
                                        level = "Fair"
                                    else:
                                        level = "Needs improvement"

                                    print(f"\nOverall Assessment:")
                                    print(f"  Average Score: {avg_score:.1f}/10 ({level})")
                                else:
                                    print(f"\nOverall Assessment:")
                                    print("  Average Score: Could not calculate (no numeric scores available)")
                            except Exception as e:
                                print(f"Could not load analysis results: {e}")

                        print("\nPress Ctrl+C to stop playback")

                        try:
                            self.recording_manager.play_recording(selected_path)
                            print("Playback completed.")
                        except KeyboardInterrupt:
                            print("\nPlayback stopped by user.")
                        except Exception as e:
                            print(f"Error during playback: {e}")

                        break
                    else:
                        print("Invalid selection. Please try again.")
                except ValueError:
                    print("Please enter a valid number or 'q' to quit.")
                except KeyboardInterrupt:
                    print("\nReturning to main menu.")
                    break

        except Exception as e:
            logger.error(f"Error in playback: {str(e)}")
            print(f"An error occurred during playback: {str(e)}")

    def start_server(self):
        """Start the UDP receiver server"""
        self.udp_receiver.start()

    async def playback_esp32_audio(self, duration=10):
        """
        Live playback of audio from ESP32 without transcription
        :param duration: Duration to listen for audio in seconds
        """
        global is_listening

        print(f"Live playback of ESP32 audio for {duration} seconds...")
        start_time = time.time()

        # Clear any existing audio in the queue
        while not audio_queue.empty():
            audio_queue.get()

        # Start listening
        self.start_esp32_listening()

        # Import required modules for audio playback
        import sounddevice as sd
        import numpy as np
        import struct

        print("[ESP32] Starting live audio playback...")

        # Play audio in real-time as it arrives
        try:
            print(f"[DEBUG] Starting playback loop for {duration}s")
            loop_count = 0
            while time.time() - start_time < duration:
                loop_count += 1
                if loop_count % 100 == 0:
                    print(f"[DEBUG] Loop iteration {loop_count}, elapsed: {time.time() - start_time:.2f}s")
                if not audio_queue.empty():
                    # Get audio chunk from queue
                    audio_chunk = audio_queue.get()
                    print(f"[DEBUG] Got audio chunk: {len(audio_chunk)} bytes")

                    # Convert raw bytes to numpy array for playback
                    # According to the ESP32 code, it processes 32-bit samples by shifting them:
                    # audioBuffer[i] >>= 13; // Remove the 8 empty bits + 6 bits of noise
                    # audioBuffer[i] <<= 3;  // Boost the signal significantly
                    # So we need to handle the processed 32-bit samples appropriately
                    if len(audio_chunk) > 0:
                        # The ESP32 sends processed 32-bit samples, but we need to convert them appropriately
                        # Each sample is 4 bytes (32-bit), and we have 2 channels (stereo)

                        # Check if the chunk length is a multiple of 4 (for 32-bit samples)
                        if len(audio_chunk) % 4 != 0:
                            # Pad with zeros if needed
                            padding_needed = 4 - (len(audio_chunk) % 4)
                            audio_chunk += b'\x00' * padding_needed

                        num_samples = len(audio_chunk) // 4  # 4 bytes per 32-bit sample
                        if num_samples > 0:
                            # Unpack as 32-bit signed integers (little-endian)
                            try:
                                audio_int32 = struct.unpack('<' + 'i' * num_samples, audio_chunk)

                                # Apply reverse processing to undo the ESP32 volume boost/shifting
                                # The ESP32 shifts right by 13 then left by 3 (net shift right by 10)
                                # We'll convert to 16-bit equivalent values
                                audio_int16 = [(val >> 10) for val in audio_int32]  # Undo the processing

                                # Convert to float32 and normalize to [-1, 1] range
                                audio_np = np.array(audio_int16, dtype=np.float32)

                                # Normalize to [-1, 1] range based on max possible value after processing
                                max_val = 32767.0  # Max value for 16-bit signed integer
                                audio_np = np.clip(audio_np, -max_val, max_val) / max_val

                                # Reshape for stereo if needed (every 2 samples form a stereo pair)
                                if self.channels == 2 and len(audio_np) % 2 == 0:
                                    audio_np = audio_np.reshape(-1, 2)

                                # Play the audio chunk with non-blocking playback to avoid delays
                                print(f"[DEBUG] Playing audio: shape={audio_np.shape}, rate={self.sample_rate}")
                                try:
                                    sd.play(audio_np, samplerate=self.sample_rate)
                                    print("[DEBUG] sd.play() succeeded")
                                except Exception as play_err:
                                    print(f"[DEBUG] sd.play() FAILED: {play_err}")
                                    raise
                                # Don't wait for playback to finish - this allows for continuous streaming
                            except struct.error as se:
                                print(f"[ESP32] Struct unpack error: {se}")
                                continue

                await asyncio.sleep(0.01)  # Small delay to prevent busy waiting

        except Exception as e:
            logger.error(f"[ESP32] Error during live audio playback: {str(e)}")
            print(f"[ESP32] Error during live audio playback: {str(e)}")
        finally:
            # Stop listening
            self.stop_esp32_listening()
            print("[ESP32] Live audio playback completed.")

    def cleanup(self):
        """
        Clean up resources
        """
        self.mic_handler.cleanup()
        self.udp_receiver.stop()


async def main():
    """
    Main entry point for the integrated speech analyzer application
    """
    logger.info("Starting Integrated Speech Analyzer with ESP32 Support...")
    print("Welcome to the Integrated Speech Analysis System with ESP32 Wireless Microphone Support!")
    print("Make sure you have set your DEEPGRAM_API_KEY in the .env file\n")
    print("For ESP32 functionality, ensure your ESP32 is configured to send audio to this machine's IP on port 1234")

    app = IntegratedSpeechAnalysisApp()
    
    # Start the UDP server for ESP32 audio
    app.start_server()

    try:
        while True:
            print("\nOptions:")
            print("1. Analyze speech (with prompt, not saved) - Microphone")
            print("2. Analyze speech (with prompt, saved) - Microphone")
            print("3. Analyze free speech (no prompt, saved) - Microphone")
            print("4. Analyze speech from ESP32 (10 seconds)")
            print("5. Analyze speech from ESP32 (custom duration)")
            print("6. Playback audio from ESP32 (without transcription)")
            print("7. Analyze speech from ESP32 with prompt")
            print("8. Playback recordings")
            print("9. Exit")

            choice = input("\nEnter your choice (1-9): ").strip()

            if choice == '1':
                duration_input = input("Enter recording duration in seconds (press Enter for default 10s): ").strip()

                if duration_input:
                    try:
                        duration = int(duration_input)
                        if duration <= 0:
                            print("Duration must be positive. Using default 10 seconds.")
                            duration = 10
                    except ValueError:
                        print("Invalid input. Using default 10 seconds.")
                        duration = 10
                else:
                    duration = None

                await app.run_analysis(duration)

            elif choice == '2':
                duration_input = input("Enter recording duration in seconds (press Enter for default 10s): ").strip()

                if duration_input:
                    try:
                        duration = int(duration_input)
                        if duration <= 0:
                            print("Duration must be positive. Using default 10 seconds.")
                            duration = 10
                    except ValueError:
                        print("Invalid input. Using default 10 seconds.")
                        duration = 10
                else:
                    duration = None

                await app.run_analysis_with_save(duration)

            elif choice == '3':
                duration_input = input("Enter recording duration in seconds (press Enter for default 10s): ").strip()

                if duration_input:
                    try:
                        duration = int(duration_input)
                        if duration <= 0:
                            print("Duration must be positive. Using default 10 seconds.")
                            duration = 10
                    except ValueError:
                        print("Invalid input. Using default 10 seconds.")
                        duration = 10
                else:
                    duration = None

                await app.run_free_analysis(duration)

            elif choice == '4':
                await app.run_esp32_analysis(duration=10)

            elif choice == '5':
                duration_input = input("Enter recording duration in seconds: ").strip()
                try:
                    duration = int(duration_input)
                    if duration <= 0:
                        print("Duration must be positive. Using default 10 seconds.")
                        duration = 10
                    await app.run_esp32_analysis(duration=duration)
                except ValueError:
                    print("Invalid input. Using default 10 seconds.")
                    await app.run_esp32_analysis(duration=10)

            elif choice == '6':
                duration_input = input("Enter playback duration in seconds (press Enter for default 10s): ").strip()
                if duration_input:
                    try:
                        duration = int(duration_input)
                        if duration <= 0:
                            print("Duration must be positive. Using default 10 seconds.")
                            duration = 10
                        await app.playback_esp32_audio(duration=duration)
                    except ValueError:
                        print("Invalid input. Using default 10 seconds.")
                        await app.playback_esp32_audio(duration=10)
                else:
                    await app.playback_esp32_audio(duration=10)

            elif choice == '7':
                duration_input = input("Enter recording duration in seconds (press Enter for default 10s): ").strip()
                if duration_input:
                    try:
                        duration = int(duration_input)
                        if duration <= 0:
                            print("Duration must be positive. Using default 10 seconds.")
                            duration = 10
                        await app.run_esp32_analysis_with_prompt(duration=duration)
                    except ValueError:
                        print("Invalid input. Using default 10 seconds.")
                        await app.run_esp32_analysis_with_prompt(duration=10)
                else:
                    await app.run_esp32_analysis_with_prompt(duration=10)

            elif choice == '8':
                await app.playback_recording()
            elif choice == '9':
                print("Thank you for using the Integrated Speech Analysis System!")
                break
            else:
                print("Invalid choice. Please enter 1, 2, 3, 4, 5, 6, 7, 8, or 9.")

    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}")
        print(f"An unexpected error occurred: {str(e)}")
    finally:
        app.cleanup()

if __name__ == "__main__":
    asyncio.run(main())