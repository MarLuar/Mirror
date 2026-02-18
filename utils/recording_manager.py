"""
Module for managing audio recordings: saving, listing, and playing back
"""
import os
import glob
import pygame
import time
from datetime import datetime
from utils.logger import setup_logger

logger = setup_logger(__name__)

class RecordingManager:
    def __init__(self, recordings_dir="recordings"):
        """
        Initialize the recording manager
        :param recordings_dir: Directory to store recordings
        """
        self.recordings_dir = recordings_dir
        os.makedirs(recordings_dir, exist_ok=True)
        
    def save_recording(self, audio_data, filename=None, audio_params=None, analysis_results=None, transcription=None):
        """
        Save audio data to a file
        :param audio_data: Audio data as bytes
        :param filename: Name for the recording file (without extension)
        :param audio_params: Dictionary with audio parameters (channels, sample_width, framerate)
        :param analysis_results: Dictionary with analysis scores
        :param transcription: Transcribed text
        :return: Path to saved file
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"recording_{timestamp}"
        
        filepath = os.path.join(self.recordings_dir, f"{filename}.wav")
        
        # If audio_params are provided, create a proper WAV file
        if audio_params:
            import wave
            with wave.open(filepath, 'wb') as wav_file:
                wav_file.setnchannels(audio_params.get('channels', 1))
                wav_file.setsampwidth(audio_params.get('sample_width', 2))
                wav_file.setframerate(audio_params.get('framerate', 44100))
                wav_file.writeframes(audio_data)
        else:
            # Fallback: write raw data (may not be playable)
            with open(filepath, 'wb') as f:
                f.write(audio_data)
        
        # Save analysis results to a companion JSON file
        if analysis_results is not None:
            import json
            json_filepath = filepath.replace('.wav', '.json')
            with open(json_filepath, 'w') as f:
                json.dump({
                    'transcription': transcription,
                    'analysis_results': analysis_results,
                    'timestamp': datetime.now().isoformat(),
                    'audio_file': os.path.basename(filepath)
                }, f, indent=2)
        
        logger.info(f"Saved recording to {filepath}")
        if analysis_results:
            logger.info(f"Saved analysis results to {filepath.replace('.wav', '.json')}")
        
        return filepath
    
    def list_recordings(self):
        """
        List all available recordings
        :return: List of file paths to recordings
        """
        pattern = os.path.join(self.recordings_dir, "*.wav")
        recordings = glob.glob(pattern)
        # Sort by modification time (newest first)
        recordings.sort(key=os.path.getmtime, reverse=True)
        return recordings
    
    def get_recording_info(self, filepath):
        """
        Get information about a recording
        :param filepath: Path to the recording file
        :return: Dictionary with recording info
        """
        filename = os.path.basename(filepath)
        size = os.path.getsize(filepath)
        mod_time = datetime.fromtimestamp(os.path.getmtime(filepath))
        
        return {
            'filename': filename,
            'filepath': filepath,
            'size': size,
            'modified': mod_time.strftime("%Y-%m-%d %H:%M:%S")
        }
    
    def play_recording(self, filepath):
        """
        Play a recording file
        :param filepath: Path to the recording file
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Recording file does not exist: {filepath}")
        
        # Check if the file is a valid WAV file before attempting to play
        try:
            import wave
            with wave.open(filepath, 'rb') as wav_file:
                # If this succeeds, it's a valid WAV file
                params = wav_file.getparams()
                logger.info(f"Playing WAV file with parameters: {params}")
        except wave.Error:
            logger.error(f"File {filepath} is not a valid WAV file")
            raise pygame.error(f"Unknown WAVE format: {filepath}")
        except Exception as e:
            logger.error(f"Error checking WAV file: {e}")
            raise pygame.error(f"Unknown WAVE format: {filepath}")
        
        # Initialize pygame mixer with appropriate settings for WAV files
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=512)
            
            # Load and play the audio file
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.play()
            
            # Wait for the audio to finish playing
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
                
        except pygame.error as e:
            logger.error(f"Pygame error playing recording: {e}")
            # Try to initialize with different parameters for compatibility
            pygame.mixer.quit()
            pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=1024)
            try:
                pygame.mixer.music.load(filepath)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    time.sleep(0.1)
            except Exception as e2:
                logger.error(f"Error playing recording after retry: {e2}")
                raise
        except Exception as e:
            logger.error(f"Error playing recording: {e}")
            raise
        finally:
            pygame.mixer.quit()