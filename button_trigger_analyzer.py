#!/usr/bin/env python3
"""
ESP32 Button Trigger Speech Analyzer
Records for duration determined by button press (toggle mode)
Press once to start, press again to stop
"""

import asyncio
import socket
import wave
import os
import sys
import time
import subprocess
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api.deepgram_client import DeepgramClientWrapper
from analysis.speech_analyzer import SpeechAnalyzer
from utils.recording_manager import RecordingManager

ESP32_IP = "10.42.0.156"
AUDIO_PORT = 1234
PROMPT_PORT = 1235
PLAYBACK_PORT = 1236

class ButtonTriggerAnalyzer:
    def __init__(self):
        self.esp32_ip = ESP32_IP
        self.audio_port = AUDIO_PORT
        self.prompt_port = PROMPT_PORT
        self.playback_port = PLAYBACK_PORT
        
        # ESP32-CAM Configuration
        self.cam_ip = "10.42.0.82"  # Update this with your CAM's IP
        self.cam_stream_url = f"http://{self.cam_ip}:81/stream"
        self.cam_control_url = f"http://{self.cam_ip}/control"
        self.cam_download_url = f"http://{self.cam_ip}:81/download"
        self.video_ffmpeg = None
        self.video_filename = None
        
        # Create sockets
        self.audio_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.audio_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.audio_sock.bind(("0.0.0.0", self.audio_port))

        self.prompt_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.prompt_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Initialize clients
        api_key = os.getenv('DEEPGRAM_API_KEY')
        if not api_key:
            raise ValueError("DEEPGRAM_API_KEY environment variable not set!")
        self.dg_client = DeepgramClientWrapper(api_key)
        self.speech_analyzer = SpeechAnalyzer()
        self.recording_manager = RecordingManager()
        
        print("=" * 60)
        print("ESP32 Button Trigger Speech Analyzer")
        print("=" * 60)
        print(f"ESP32 IP: {self.esp32_ip}")
        print(f"Audio Port: {self.audio_port}")
        print(f"Prompt Port: {self.prompt_port}")
        print(f"Playback Port: {self.playback_port}")
        print(f"ESP32-CAM IP: {self.cam_ip}")
        print("=" * 60)
        print("\nWaiting for ESP32 to start recording...")
        print("(Press button on ESP32 to start/stop recording)")
    
    def send_prompt(self, message):
        """Send message to ESP32 display"""
        try:
            self.prompt_sock.sendto(message.encode(), (self.esp32_ip, self.prompt_port))
            print(f"Sent to ESP32: {message[:50]}...")
        except Exception as e:
            print(f"Failed to send: {e}")
    
    def send_show_prompts(self):
        """Tell ESP32 to show 3 new prompts"""
        self.send_prompt("SHOW_PROMPTS")
    
    def send_waiting(self):
        """Tell ESP32 to show waiting state"""
        self.send_prompt("WAITING")
    
    def receive_audio_until_stop(self):
        """Receive audio from ESP32 until STOP message received"""
        print("\n[Button Trigger] Receiving audio...")
        
        audio_buffer = bytearray()
        recording_started = False
        start_time = time.time()
        
        self.audio_sock.settimeout(5.0)  # 5 second socket timeout
        
        last_data_time = time.time()
        no_data_timeout = 10  # If no data for 10 seconds, consider recording done
        
        while True:
            try:
                data, addr = self.audio_sock.recvfrom(4096)
                last_data_time = time.time()
                
                # Check for control messages
                if len(data) < 100:
                    try:
                        msg = data.decode('utf-8')
                        
                        # START message - recording started
                        if msg.startswith("START"):
                            print("[Button Trigger] Recording started by ESP32")
                            recording_started = True
                            start_time = time.time()
                            continue
                        
                        # STOP message - recording stopped
                        if msg.startswith("STOP"):
                            duration_ms = int(msg.split(":")[1]) if ":" in msg else 0
                            print(f"\n[Button Trigger] Recording stopped: {duration_ms}ms")
                            recording_started = False
                            break
                            
                    except:
                        pass
                
                # Audio data
                if recording_started or len(audio_buffer) > 0:
                    audio_buffer.extend(data)
                    if not recording_started:
                        recording_started = True
                        print("[Button Trigger] First audio data received...")
                
                # Progress update every 5 seconds
                if recording_started:
                    elapsed = time.time() - start_time
                    if int(elapsed) % 5 == 0 and int(elapsed) > 0:
                        received_sec = len(audio_buffer) / (44100 * 2 * 2)
                        print(f"[Button Trigger] Progress: {elapsed:.1f}s elapsed, {received_sec:.1f}s audio received")
                    
            except socket.timeout:
                # Check if we've lost connection
                time_since_last_data = time.time() - last_data_time
                
                if time_since_last_data > no_data_timeout:
                    print(f"[Button Trigger] No data for {time_since_last_data:.1f}s, finishing...")
                    break
        
        self.audio_sock.settimeout(None)
        
        duration_sec = len(audio_buffer) / (44100 * 2 * 2)  # 44100 Hz, 2 channels, 2 bytes
        print(f"[Button Trigger] Received {len(audio_buffer)} bytes ({duration_sec:.2f}s)")
        
        return bytes(audio_buffer)
    
    def save_audio(self, audio_data, filename):
        """Save audio to WAV file in recordings/raw/ folder"""
        raw_dir = os.path.join("recordings", "raw")
        if not os.path.exists(raw_dir):
            os.makedirs(raw_dir)
        
        filepath = os.path.join(raw_dir, filename)
        
        with wave.open(filepath, 'wb') as wav:
            wav.setnchannels(2)
            wav.setsampwidth(2)
            wav.setframerate(44100)
            wav.writeframes(audio_data)
        
        return filepath
    
    async def transcribe(self, audio_data):
        """Transcribe audio using Deepgram"""
        print("\n[Button Trigger] Transcribing...")
        
        try:
            transcription = await self.dg_client.transcribe_audio_from_bytes_with_retry(
                audio_data,
                sample_rate=44100,
                channels=2,
                sample_width=2
            )
            print(f"[Button Trigger] Transcription: {transcription}")
            return transcription
        except Exception as e:
            print(f"[Button Trigger] Transcription error: {e}")
            return ""
    
    def analyze(self, transcription):
        """Analyze speech"""
        print("\n[Button Trigger] Analyzing speech...")
        
        results = self.speech_analyzer.analyze_speech(transcription, None)
        
        # Calculate average
        numeric = [v for v in results.values() if isinstance(v, (int, float))]
        avg = sum(numeric) / len(numeric) if numeric else 0
        
        print(f"\n{'='*60}")
        print("SPEECH ANALYSIS RESULTS")
        print(f"{'='*60}")
        print(f"Transcription: {transcription}")
        for aspect, score in results.items():
            if isinstance(score, str):
                print(f"  {aspect.capitalize()}: {score}")
            else:
                print(f"  {aspect.capitalize()}: {score:.1f}/10")
        print(f"  Average: {avg:.1f}/10")
        print(f"{'='*60}\n")
        
        return results, avg
    
    def generate_improvements(self, results):
        """Generate constructive improvement suggestions"""
        
        # Extract scores with defaults
        pron = results.get('pronunciation', 5)
        artic = results.get('articulation', 5)
        pace = results.get('pace', 5)
        clarity = results.get('clarity', 5)
        
        suggestions = []
        
        # Pronunciation feedback
        if pron < 7:
            if pron < 4:
                suggestions.append("pronunciation needs work - slow down and articulate each word")
            else:
                suggestions.append("practice difficult words and focus on ending sounds")
        
        # Articulation feedback
        if artic < 7:
            if artic < 4:
                suggestions.append("open your mouth more and exaggerate mouth movements")
            else:
                suggestions.append("work on consonant clarity - don't mumble word endings")
        
        # Pace feedback
        if pace < 7:
            if pace < 4:
                suggestions.append("speak more steadily - avoid rushing through sentences")
            else:
                suggestions.append("use pauses between phrases - don't rush")
        
        # Clarity feedback
        if clarity < 7:
            if clarity < 4:
                suggestions.append("speak louder and closer to the microphone")
            else:
                suggestions.append("project your voice and reduce filler words")
        
        if not suggestions:
            return "Good delivery. Minor refinements only."
        
        # Return top 2 suggestions max (to fit on screen)
        if len(suggestions) == 1:
            return f"Improve: {suggestions[0]}"
        else:
            return f"Improve: {suggestions[0]}. Also: {suggestions[1]}"
    
    def check_cam_status(self):
        """Check ESP32-CAM status to diagnose recording issues"""
        import urllib.request
        import json
        
        try:
            status_url = f"http://{self.cam_ip}/status"
            req = urllib.request.Request(status_url, timeout=5)
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())
                return data
        except Exception as e:
            print(f"[Camera] Status check failed: {e}")
            return None
    
    def download_video_from_cam(self, output_dir="recordings/raw", max_retries=5):
        """Download recorded video from ESP32-CAM SD card with robust retry logic and OLED progress"""
        import urllib.request
        import os
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # First check camera status
        print("[Video] Checking camera status...")
        print("[Video] IMPORTANT: If no recording found, check:")
        print("  1. ESP32-CAM MAC address matches main_firmware config")
        print("  2. Both devices connected to same WiFi")
        print("  3. Camera has SD card inserted")
        status = self.check_cam_status()
        if status:
            print(f"[Camera] SD Card: {'OK' if status.get('sd_card_available') else 'NOT FOUND'}")
            print(f"[Camera] Recording Active: {'YES' if status.get('recording_active') else 'NO'}")
            print(f"[Camera] Recording Requested: {'YES' if status.get('recording_requested') else 'NO'}")
            print(f"[Camera] Frames Recorded: {status.get('frames_recorded', 0)}")
            print(f"[Camera] Current File: {status.get('current_file', 'NONE')}")
            print(f"[Camera] File Downloaded: {'YES' if status.get('file_downloaded') else 'NO'}")
            
            if not status.get('sd_card_available'):
                print("[Video] ERROR: Camera SD card not available!")
                return None
            if status.get('recording_active'):
                print("[Video] WARNING: Camera still recording, waiting...")
                time.sleep(2)
            if status.get('file_downloaded'):
                print("[Video] ERROR: Video already downloaded!")
                return None
            if status.get('frames_recorded', 0) == 0:
                print("[Video] ERROR: No frames recorded!")
        else:
            print("[Video] WARNING: Could not check camera status")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        mjpeg_filename = os.path.join(output_dir, f"video_{timestamp}.mjpeg")
        mp4_filename = os.path.join(output_dir, f"video_{timestamp}.mp4")
        
        print(f"[Video] Downloading from ESP32-CAM SD card...")
        
        # Notify ESP32 that download is starting
        self.send_prompt("DOWNLOAD:0")
        
        # Try simple HTTP download with retries
        downloaded_size = 0
        min_usable_size = 50000  # 50KB minimum for a valid video
        
        for attempt in range(max_retries):
            try:
                # Use urllib with custom opener for better control
                req = urllib.request.Request(
                    self.cam_download_url,
                    headers={
                        'Connection': 'close',  # Don't keep connection open
                        'Accept': '*/*'
                    }
                )
                
                # Open connection with short timeout
                with urllib.request.urlopen(req, timeout=10) as response:
                    content_length = response.headers.get('Content-Length')
                    total_size = int(content_length) if content_length else 0
                    
                    if total_size > 0:
                        print(f"[Video] File size: {total_size / 1024 / 1024:.2f} MB")
                    
                    # Read data in chunks with error handling
                    chunk_size = 8192
                    downloaded_size = 0
                    max_failures = 100  # Allow many small read failures
                    failures = 0
                    last_progress_percent = -1  # Track last sent progress
                    
                    with open(mjpeg_filename, 'wb') as f:
                        while True:
                            try:
                                chunk = response.read(chunk_size)
                                if not chunk:
                                    break
                                f.write(chunk)
                                downloaded_size += len(chunk)
                                failures = 0  # Reset failure count on success
                                
                                # Send progress to OLED every 5% or every 256KB
                                if total_size > 0:
                                    percent = int((downloaded_size * 100) / total_size)
                                    # Send update every 5% change
                                    if percent != last_progress_percent and percent % 5 == 0:
                                        self.send_prompt(f"DOWNLOAD:{percent}")
                                        last_progress_percent = percent
                                else:
                                    # Unknown total size - show KB downloaded
                                    if downloaded_size % (256 * 1024) == 0:
                                        kb_downloaded = int(downloaded_size / 1024)
                                        self.send_prompt(f"DOWNLOAD:{kb_downloaded}KB")
                                
                                if downloaded_size % (256 * 1024) == 0:
                                    print(f"[Video] Downloaded: {downloaded_size / 1024:.1f} KB")
                                    
                            except Exception as read_err:
                                failures += 1
                                if failures > max_failures:
                                    print(f"[Video] Too many read failures, giving up")
                                    break
                                continue  # Try to keep reading
                
                # Check if download is usable
                if downloaded_size >= min_usable_size:
                    print(f"[Video] Downloaded: {mjpeg_filename} ({downloaded_size / 1024:.1f} KB)")
                    # Send 100% completion
                    self.send_prompt("DOWNLOAD:100")
                    time.sleep(0.5)  # Let user see 100% on OLED
                    # Return to waiting state
                    self.send_waiting()
                    break  # Success
                else:
                    print(f"[Video] Download too small ({downloaded_size} bytes), retrying...")
                    if os.path.exists(mjpeg_filename):
                        os.remove(mjpeg_filename)
                    
            except Exception as e:
                print(f"[Video] Download attempt {attempt + 1}/{max_retries} failed: {str(e)[:80]}")
                if os.path.exists(mjpeg_filename):
                    os.remove(mjpeg_filename)
                
                if attempt < max_retries - 1:
                    wait_time = 1 + attempt  # 1, 2, 3, 4, 5 seconds
                    print(f"[Video] Retrying in {wait_time} seconds...")
                    # Show retry message on OLED
                    self.send_prompt(f"DOWNLOAD:Retry{attempt+1}")
                    time.sleep(wait_time)
                else:
                    print(f"[Video] All download attempts failed")
                    self.send_prompt("DOWNLOAD:Failed")
                    return None
        
        # Check final result
        if downloaded_size < min_usable_size:
            print(f"[Video] Download failed - file too small ({downloaded_size} bytes)")
            if os.path.exists(mjpeg_filename):
                os.remove(mjpeg_filename)
            return None
        
        # Convert MJPEG to MP4
        try:
            print("[Video] Converting to MP4...")
            convert_cmd = [
                "ffmpeg",
                "-hide_banner",
                "-loglevel", "error",
                "-f", "mjpeg",
                "-framerate", "15",  # Input frame rate (matches camera recording)
                "-i", mjpeg_filename,
                "-c:v", "libx264",
                "-r", "15",          # Output frame rate
                "-preset", "ultrafast",
                "-crf", "23",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                "-y",
                mp4_filename
            ]
            
            subprocess.run(convert_cmd, check=True)
            os.remove(mjpeg_filename)
            
            size_mb = os.path.getsize(mp4_filename) / (1024 * 1024)
            print(f"[Video] Saved: {mp4_filename} ({size_mb:.2f} MB)")
            return mp4_filename
            
        except Exception as e:
            print(f"[Video] Conversion failed: {e}")
            if os.path.exists(mjpeg_filename):
                os.remove(mjpeg_filename)
            return None
    
    def send_playback(self, wav_path):
        """Send audio back to ESP32 for playback"""
        print("\n[Button Trigger] Sending playback...")
        
        try:
            with wave.open(wav_path, 'rb') as wav:
                audio_data = wav.readframes(wav.getnframes())
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            # Send START
            for _ in range(3):
                sock.sendto(b"START", (self.esp32_ip, self.playback_port))
                time.sleep(0.1)
            
            # Send audio in chunks
            chunk_size = 1024
            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i:i+chunk_size]
                sock.sendto(chunk, (self.esp32_ip, self.playback_port))
                time.sleep(0.005)
            
            # Send END
            for _ in range(5):
                sock.sendto(b"END", (self.esp32_ip, self.playback_port))
                time.sleep(0.1)
            
            sock.close()
            print("[Button Trigger] Playback sent")
            
            # Wait for ESP32 to restart
            print("[Button Trigger] Waiting for ESP32 to restart...")
            time.sleep(12)
            
            # Tell ESP32 to show prompts again
            self.send_show_prompts()
            
        except Exception as e:
            print(f"[Button Trigger] Playback error: {e}")
    
    # ========== OPTION 3: Audio via CAM SD + ESP-NOW ==========
    
    def send_audio_to_cam(self, wav_path, filename="playback.wav"):
        """Send audio file to ESP32-CAM for storage on SD card"""
        import urllib.request
        
        print(f"\n[Option 3] Sending audio to CAM SD card: {filename}")
        
        try:
            # Read audio file
            with open(wav_path, 'rb') as f:
                audio_data = f.read()
            
            # Build URL
            url = f"http://{self.cam_ip}/audio_upload?file={filename}"
            
            # Create request
            req = urllib.request.Request(
                url,
                data=audio_data,
                headers={'Content-Type': 'application/octet-stream'},
                method='POST'
            )
            
            # Send
            with urllib.request.urlopen(req, timeout=30) as response:
                result = response.read().decode()
                print(f"[Option 3] CAM response: {result}")
                return True
                
        except Exception as e:
            print(f"[Option 3] Failed to send audio to CAM: {e}")
            return False
    
    def play_audio_from_cam(self):
        """Trigger ESP32-CAM to stream audio via ESP-NOW to main ESP32"""
        import urllib.request
        
        print("\n[Option 3] Triggering playback from CAM via ESP-NOW...")
        
        try:
            url = f"http://{self.cam_ip}/audio_play"
            
            with urllib.request.urlopen(url, timeout=10) as response:
                result = response.read().decode()
                print(f"[Option 3] CAM response: {result}")
                
                # Wait for playback to complete (approximate)
                print("[Option 3] Waiting for playback to complete...")
                time.sleep(8)  # Wait for ESP-NOW transfer + playback
                
                return True
                
        except Exception as e:
            print(f"[Option 3] Failed to trigger playback: {e}")
            return False
    
    async def process_recording(self, audio_data):
        """Process a complete recording - returns audio file path for video stitching"""
        if len(audio_data) < 1000:
            print("[Button Trigger] Audio too short, skipping")
            self.send_show_prompts()
            return None
        
        # Save recording
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"button_trigger_{timestamp}.wav"
        wav_path = self.save_audio(audio_data, filename)
        print(f"[Button Trigger] Saved: {filename}")
        
        # Transcribe
        transcription = await self.transcribe(audio_data)
        if not transcription:
            print("[Button Trigger] No transcription, skipping analysis")
            self.send_show_prompts()
            return
        
        # Analyze
        results, avg = self.analyze(transcription)
        
        # Send detailed scores to ESP32
        # Format: "Overall|Category1:Score1|Category2:Score2|..."
        detailed_scores = f"{avg:.0f}"
        for aspect, score in results.items():
            if isinstance(score, (int, float)):
                # Shorten category names for OLED display
                short_name = aspect[:6]  # Max 6 chars
                detailed_scores += f"|{short_name}:{score:.0f}"
        score_msg = f"SCORE:{detailed_scores}"
        self.send_prompt(score_msg)
        time.sleep(5)
        
        # Send improvements
        improvements = self.generate_improvements(results)
        improve_msg = f"IMPROVE:{improvements}"
        self.send_prompt(improve_msg)
        
        # Wait for ESP32 to finish displaying feedback (5s) + setup time (1s)
        print("[Button Trigger] Waiting for feedback display...")
        time.sleep(6)
        
        # Send playback
        self.send_playback(wav_path)
        
        # Return audio path for video stitching
        return wav_path
    
    def combine_audio_video(self, audio_path, video_path, output_path=None):
        """Combine audio (WAV) and video (MP4) into a single MP4 file using ffmpeg"""
        import subprocess
        import os
        
        if not audio_path or not os.path.exists(audio_path):
            print("[Combine] Audio file not found")
            return None
        if not video_path or not os.path.exists(video_path):
            print("[Combine] Video file not found")
            return None
        
        # Generate output filename if not provided - save to recordings/final/
        if not output_path:
            final_dir = os.path.join("recordings", "final")
            if not os.path.exists(final_dir):
                os.makedirs(final_dir)
            
            # Get timestamp from audio filename
            audio_basename = os.path.basename(audio_path)
            timestamp = audio_basename.replace("button_trigger_", "").replace(".wav", "")
            output_path = os.path.join(final_dir, f"combined_{timestamp}.mp4")
        
        print(f"[Combine] Combining audio + video...")
        print(f"[Combine] Audio: {audio_path}")
        print(f"[Combine] Video: {video_path}")
        
        try:
            # ffmpeg command to mux audio and video
            # -shortest: end when shortest input ends (in case audio/video lengths differ)
            # -c:v copy: copy video stream (no re-encode)
            # -c:a aac: encode audio to AAC
            # -b:a 128k: audio bitrate
            combine_cmd = [
                "ffmpeg",
                "-hide_banner",
                "-loglevel", "error",
                "-i", video_path,      # Video input
                "-i", audio_path,      # Audio input
                "-c:v", "copy",        # Copy video (no re-encode)
                "-c:a", "aac",         # Encode audio to AAC
                "-b:a", "128k",        # Audio bitrate
                "-ar", "44100",        # Audio sample rate
                "-shortest",           # End when shortest input ends
                "-movflags", "+faststart",
                "-y",                  # Overwrite output
                output_path
            ]
            
            subprocess.run(combine_cmd, check=True)
            
            # Get file size
            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            print(f"[Combine] Success! Saved: {output_path} ({size_mb:.2f} MB)")
            
            return output_path
            
        except subprocess.CalledProcessError as e:
            print(f"[Combine] ffmpeg failed: {e}")
            return None
        except Exception as e:
            print(f"[Combine] Error: {e}")
            return None
    
    async def run(self):
        """Main loop"""
        print("\n[Button Trigger] Ready for recordings")
        print("Press button on ESP32 to START recording")
        print("Press button again to STOP recording\n")
        
        while True:
            try:
                # Wait for START message from ESP32
                print("Waiting for recording to start...")
                self.audio_sock.settimeout(None)
                
                audio_buffer = bytearray()
                recording_started = False
                
                while True:
                    data, addr = self.audio_sock.recvfrom(4096)
                    
                    # Check for control messages
                    if len(data) < 100:
                        try:
                            msg = data.decode('utf-8')
                            
                            # START message
                            if msg.startswith("START"):
                                print("\n[Button Trigger] Recording started!")
                                recording_started = True
                                continue
                            
                            # STOP message - marks end of recording
                            if msg.startswith("STOP"):
                                duration_ms = int(msg.split(":")[1]) if ":" in msg else 0
                                print(f"[Button Trigger] Recording complete: {duration_ms}ms")
                                recording_started = False
                                break
                                
                        except:
                            pass
                    
                    # Audio data
                    if recording_started:
                        audio_buffer.extend(data)
                
                # Process the recording
                if len(audio_buffer) > 0:
                    audio_file = await self.process_recording(bytes(audio_buffer))
                    
                    # Wait for camera to finish writing file
                    print("\n[Video] Waiting for camera to finalize recording...")
                    time.sleep(2)
                    
                    # Download video from ESP32-CAM SD card after audio processing
                    print("[Video] Retrieving video from ESP32-CAM...")
                    video_file = self.download_video_from_cam()
                    if video_file:
                        print(f"[Video] Video saved: {video_file}")
                        
                        # Combine audio and video if both exist
                        if audio_file and os.path.exists(audio_file):
                            print("\n[Combine] Stitching audio and video together...")
                            combined_file = self.combine_audio_video(audio_file, video_file)
                            if combined_file:
                                print(f"[Combine] Final video with audio: {combined_file}")
                            else:
                                print("[Combine] Failed to combine audio and video")
                    else:
                        print("[Video] Failed to retrieve video")
                else:
                    print("[Button Trigger] No audio received")
                    self.send_show_prompts()
                
            except Exception as e:
                print(f"[Button Trigger] Error: {e}")
                time.sleep(1)

async def main():
    analyzer = ButtonTriggerAnalyzer()
    await analyzer.run()

if __name__ == "__main__":
    asyncio.run(main())
