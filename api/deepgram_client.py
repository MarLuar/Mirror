import asyncio
from deepgram import DeepgramClient
from deepgram.clients.common.v1.options import BufferSource
from utils.logger import setup_logger
import io
import wave
import os

logger = setup_logger(__name__)

class DeepgramClientWrapper:
    def __init__(self, api_key):
        """
        Initialize the Deepgram client wrapper
        :param api_key: Deepgram API key
        """
        if not api_key:
            raise ValueError("Deepgram API key is required")

        # Pass the API key directly to AsyncDeepgramClient
        self.client = DeepgramClient(api_key)

    async def transcribe_audio(self, audio_data):
        """
        Transcribe audio data using Deepgram
        :param audio_data: Audio data as bytes
        :return: Transcribed text
        """
        try:
            # Define options for the transcription
            options = {
                'punctuate': True,
                'language': 'en-US'
            }

            # The audio data from PyAudio needs to be wrapped in a proper WAV format
            # Create a WAV file in memory with the proper headers
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wav_file:
                # Configure for the same format as the microphone handler
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit (2 bytes)
                wav_file.setframerate(44100)  # 44.1kHz
                wav_file.writeframes(audio_data)

            # Get the WAV formatted bytes
            wav_bytes = wav_buffer.getvalue()

            # Call the Deepgram API using the correct method for WAV audio data
            source = BufferSource(buffer=wav_bytes)
            response = self.client.listen.rest.v("1").transcribe_file(
                source=source,
                options=options
            )

            # Extract transcript from response
            transcript = response.results.channels[0].alternatives[0].transcript
            return transcript
        except Exception as e:
            logger.error(f"Error transcribing audio: {str(e)}")
            raise

    async def transcribe_audio_from_bytes(self, audio_bytes, sample_rate=44100, channels=2, sample_width=2):
        """
        Transcribe audio data from raw bytes (for ESP32 audio)
        :param audio_bytes: Raw audio bytes
        :param sample_rate: Sample rate of the audio (default 44100 for ESP32)
        :param channels: Number of channels (default 2 for stereo as per ESP32 config)
        :param sample_width: Sample width in bytes (default 2 for 16-bit)
        :return: Transcribed text
        """
        try:
            # Define options for the transcription
            options = {
                'punctuate': True,
                'language': 'en-US'
            }

            # Create a WAV file in memory with the proper headers for ESP32 audio
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(channels)
                wav_file.setsampwidth(sample_width)
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(audio_bytes)

            # Get the WAV formatted bytes
            wav_bytes = wav_buffer.getvalue()

            # Call the Deepgram API using the correct method for WAV audio data
            source = BufferSource(buffer=wav_bytes)
            response = self.client.listen.rest.v("1").transcribe_file(
                source=source,
                options=options
            )

            # Extract transcript from response
            transcript = response.results.channels[0].alternatives[0].transcript
            return transcript
        except Exception as e:
            logger.error(f"Error transcribing audio from bytes: {str(e)}")
            raise

    async def transcribe_audio_from_bytes_with_retry(self, audio_bytes, sample_rate=44100, channels=2, sample_width=2, max_retries=3):
        """
        Transcribe audio data from raw bytes with automatic retry on timeout
        :param audio_bytes: Raw audio bytes
        :param sample_rate: Sample rate of the audio (default 44100 for ESP32)
        :param channels: Number of channels (default 2 for stereo as per ESP32 config)
        :param sample_width: Sample width in bytes (default 2 for 16-bit)
        :param max_retries: Maximum number of retries with reduced buffer
        :return: Transcribed text
        """
        current_buffer = audio_bytes
        retries = 0

        while retries <= max_retries:
            try:
                # Try to transcribe the current buffer
                return await self.transcribe_audio_from_bytes(current_buffer, sample_rate, channels, sample_width)
            except Exception as e:
                if "timeout" in str(e).lower() and retries < max_retries:
                    # Reduce the buffer size by half for the next attempt
                    current_buffer = current_buffer[:len(current_buffer)//2]
                    if len(current_buffer) == 0:
                        # If we've reduced to zero, we can't continue
                        logger.error("Audio buffer reduced to zero, cannot continue")
                        raise e
                    retries += 1
                    logger.warning(f"Timeout occurred, reducing buffer size and retrying ({retries}/{max_retries})")
                else:
                    # Either not a timeout error or max retries reached
                    raise e