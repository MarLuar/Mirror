import pyaudio
import wave
import numpy as np
import asyncio
from utils.logger import setup_logger
import io

logger = setup_logger(__name__)

class MicrophoneHandler:
    def __init__(self):
        """
        Initialize the microphone handler
        """
        self.audio = pyaudio.PyAudio()
        self.chunk_size = 1024
        self.sample_format = pyaudio.paInt16
        self.channels = 1
        self.fs = 44100  # Sampling rate

    async def record_audio(self, duration=5):
        """
        Record audio from microphone for specified duration
        :param duration: Recording duration in seconds
        :return: Audio data as bytes
        """
        logger.info(f"Recording audio for {duration} seconds...")

        stream = self.audio.open(
            format=self.sample_format,
            channels=self.channels,
            rate=self.fs,
            frames_per_buffer=self.chunk_size,
            input=True
        )

        frames = []
        total_frames = int(self.fs / self.chunk_size * duration)

        for i in range(total_frames):
            data = stream.read(self.chunk_size)
            frames.append(data)

        stream.stop_stream()
        stream.close()

        # Combine frames into a single byte string
        audio_data = b''.join(frames)

        logger.info("Audio recording completed.")
        return audio_data

    def save_recording_to_wav(self, audio_data, filepath):
        """
        Save raw audio data to a WAV file
        :param audio_data: Raw audio data as bytes
        :param filepath: Path to save the WAV file
        """
        with wave.open(filepath, 'wb') as wav_file:
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(self.audio.get_sample_size(self.sample_format))
            wav_file.setframerate(self.fs)
            wav_file.writeframes(audio_data)

    def cleanup(self):
        """
        Clean up resources
        """
        self.audio.terminate()