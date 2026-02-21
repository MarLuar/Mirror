#!/usr/bin/env python3
"""
ESP32 Button Hold Speech Analyzer
Records for duration determined by button hold time
"""

import asyncio
import socket
import wave
import os
import sys
import time
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

class ButtonHoldAnalyzer:
    def __init__(self):
        self.esp32_ip = ESP32_IP
        self.audio_port = AUDIO_PORT
        self.prompt_port = PROMPT_PORT
        self.playback_port = PLAYBACK_PORT
        
        # Create sockets
        self.audio_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.audio_sock.bind(("0.0.0.0", self.audio_port))
        
        self.prompt_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Initialize clients
        api_key = os.getenv('DEEPGRAM_API_KEY')
        if not api_key:
            raise ValueError("DEEPGRAM_API_KEY environment variable not set!")
        self.dg_client = DeepgramClientWrapper(api_key)
        self.speech_analyzer = SpeechAnalyzer()
        self.recording_manager = RecordingManager()
        
        print("=" * 60)
        print("ESP32 Button Hold Speech Analyzer")
        print("=" * 60)
        print(f"ESP32 IP: {self.esp32_ip}")
        print(f"Audio Port: {self.audio_port}")
        print(f"Prompt Port: {self.prompt_port}")
        print(f"Playback Port: {self.playback_port}")
        print("=" * 60)
        print("\nWaiting for ESP32 to start recording...")
        print("(Hold button on ESP32 to record)")
    
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
    
    def receive_audio(self, duration_ms):
        """Receive audio from ESP32 for specified duration"""
        print(f"\n[Button Hold] Receiving audio for {duration_ms}ms...")
        
        audio_buffer = bytearray()
        start_time = time.time()
        timeout = (duration_ms / 1000.0) + 5  # Add 5s buffer
        
        self.audio_sock.settimeout(1.0)
        
        while (time.time() - start_time) < timeout:
            try:
                data, addr = self.audio_sock.recvfrom(4096)
                
                # Check for DURATION message
                if len(data) < 100:
                    try:
                        msg = data.decode('utf-8')
                        if msg.startswith("DURATION:"):
                            continue  # Skip duration messages
                    except:
                        pass
                
                audio_buffer.extend(data)
                
                # Progress update every second
                elapsed = time.time() - start_time
                if int(elapsed) > 0 and int(elapsed) % 1 == 0:
                    pass  # Could add progress here
                    
            except socket.timeout:
                # Check if we've received enough audio
                if len(audio_buffer) > 0 and (time.time() - start_time) > (duration_ms / 1000.0):
                    break
        
        self.audio_sock.settimeout(None)
        
        duration_sec = len(audio_buffer) / (44100 * 2 * 2)  # 44100 Hz, 2 channels, 2 bytes
        print(f"[Button Hold] Received {len(audio_buffer)} bytes ({duration_sec:.2f}s)")
        
        return bytes(audio_buffer)
    
    def save_audio(self, audio_data, filename):
        """Save audio to WAV file"""
        filepath = os.path.join("recordings", filename)
        
        with wave.open(filepath, 'wb') as wav:
            wav.setnchannels(2)
            wav.setsampwidth(2)
            wav.setframerate(44100)
            wav.writeframes(audio_data)
        
        return filepath
    
    async def transcribe(self, audio_data):
        """Transcribe audio using Deepgram"""
        print("\n[Button Hold] Transcribing...")
        
        try:
            transcription = await self.dg_client.transcribe_audio_from_bytes_with_retry(
                audio_data,
                sample_rate=44100,
                channels=2,
                sample_width=2
            )
            print(f"[Button Hold] Transcription: {transcription}")
            return transcription
        except Exception as e:
            print(f"[Button Hold] Transcription error: {e}")
            return ""
    
    def analyze(self, transcription):
        """Analyze speech"""
        print("\n[Button Hold] Analyzing speech...")
        
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
        """Generate improvement suggestions"""
        suggestions = []
        
        if results.get('pronunciation', 10) < 6:
            suggestions.append("Practice pronunciation")
        if results.get('articulation', 10) < 6:
            suggestions.append("Focus on clearer words")
        if results.get('pace', 10) < 6:
            suggestions.append("Work on speaking speed")
        if results.get('clarity', 10) < 6:
            suggestions.append("Speak louder/clearer")
        
        if suggestions:
            return " ".join(suggestions)
        return "Great job! Keep practicing!"
    
    def send_playback(self, wav_path):
        """Send audio back to ESP32 for playback"""
        print("\n[Button Hold] Sending playback...")
        
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
            print("[Button Hold] Playback sent")
            
            # Wait for ESP32 to restart
            print("[Button Hold] Waiting for ESP32 to restart...")
            time.sleep(12)
            
            # Tell ESP32 to show prompts again
            self.send_show_prompts()
            
        except Exception as e:
            print(f"[Button Hold] Playback error: {e}")
    
    async def process_recording(self, audio_data):
        """Process a complete recording"""
        if len(audio_data) < 1000:
            print("[Button Hold] Audio too short, skipping")
            self.send_show_prompts()
            return
        
        # Save recording
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"button_hold_{timestamp}.wav"
        wav_path = self.save_audio(audio_data, filename)
        print(f"[Button Hold] Saved: {filename}")
        
        # Transcribe
        transcription = await self.transcribe(audio_data)
        if not transcription:
            print("[Button Hold] No transcription, skipping analysis")
            self.send_show_prompts()
            return
        
        # Analyze
        results, avg = self.analyze(transcription)
        
        # Send score to ESP32
        score_msg = f"SCORE:{avg:.1f}"
        self.send_prompt(score_msg)
        time.sleep(3)
        
        # Send improvements
        improvements = self.generate_improvements(results)
        improve_msg = f"IMPROVE:{improvements}"
        self.send_prompt(improve_msg)
        
        # Send playback
        self.send_playback(wav_path)
    
    async def run(self):
        """Main loop"""
        print("\n[Button Hold] Ready for recordings")
        print("Hold button on ESP32 to record, release to stop\n")
        
        while True:
            try:
                # Wait for duration message from ESP32
                print("Waiting for recording...")
                self.audio_sock.settimeout(None)
                
                duration_ms = None
                audio_buffer = bytearray()
                recording_started = False
                
                while True:
                    data, addr = self.audio_sock.recvfrom(4096)
                    
                    # Check for DURATION message (marks end of recording)
                    if len(data) < 50:
                        try:
                            msg = data.decode('utf-8')
                            if msg.startswith("DURATION:"):
                                duration_ms = int(msg.split(":")[1])
                                print(f"\n[Button Hold] Recording complete: {duration_ms}ms")
                                recording_started = False
                                break
                        except:
                            pass
                    
                    # If we get here, it's audio data
                    if not recording_started:
                        print("[Button Hold] Recording started...")
                        recording_started = True
                    
                    audio_buffer.extend(data)
                
                # Process the recording
                if len(audio_buffer) > 0:
                    await self.process_recording(bytes(audio_buffer))
                else:
                    print("[Button Hold] No audio received")
                    self.send_show_prompts()
                
            except Exception as e:
                print(f"[Button Hold] Error: {e}")
                time.sleep(1)

async def main():
    analyzer = ButtonHoldAnalyzer()
    await analyzer.run()

if __name__ == "__main__":
    asyncio.run(main())
