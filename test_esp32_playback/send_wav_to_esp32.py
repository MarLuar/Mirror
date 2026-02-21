#!/usr/bin/env python3
"""
Send WAV file to ESP32 via UDP for playback

Usage:
    python send_wav_to_esp32.py <wav_file>
    
Example:
    python send_wav_to_esp32.py /home/koogs/Documents/Mirror/speech-analyzer/recordings/esp32_prompted_speech_20260221_193100.wav
"""

import socket
import sys
import time
import wave
import os

# ESP32 Configuration
ESP32_IP = "10.42.0.156"  # Update this with your ESP32's actual IP
ESP32_PORT = 1235         # Port ESP32 listens on

def send_wav_file(wav_path):
    """Send a WAV file to ESP32 for playback"""
    
    # Check if file exists
    if not os.path.exists(wav_path):
        print(f"Error: File not found: {wav_path}")
        sys.exit(1)
    
    # Open and analyze WAV file
    print(f"Opening WAV file: {wav_path}")
    try:
        with wave.open(wav_path, 'rb') as wav:
            channels = wav.getnchannels()
            sample_width = wav.getsampwidth()
            frame_rate = wav.getframerate()
            n_frames = wav.getnframes()
            duration = n_frames / frame_rate
            
            print(f"\nWAV File Info:")
            print(f"  Channels: {channels}")
            print(f"  Sample Width: {sample_width} bytes ({sample_width * 8}-bit)")
            print(f"  Frame Rate: {frame_rate} Hz")
            print(f"  Total Frames: {n_frames}")
            print(f"  Duration: {duration:.2f} seconds")
            
            # Read all audio data
            print("\nReading audio data...")
            audio_data = wav.readframes(n_frames)
            print(f"  Read {len(audio_data)} bytes")
    except Exception as e:
        print(f"Error reading WAV file: {e}")
        sys.exit(1)
    
    # Create UDP socket
    print(f"\nConnecting to ESP32 at {ESP32_IP}:{ESP32_PORT}")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(5.0)
    
    # Test connectivity first with a BEEP command
    print("Sending test BEEP command...")
    sock.sendto(b"BEEP", (ESP32_IP, ESP32_PORT))
    time.sleep(0.5)
    
    # Send audio data in chunks
    chunk_size = 1024  # Bytes per packet
    total_sent = 0
    packet_count = 0
    
    print(f"\nSending audio data in {chunk_size}-byte chunks...")
    print("=" * 50)
    
    start_time = time.time()
    
    for i in range(0, len(audio_data), chunk_size):
        chunk = audio_data[i:i+chunk_size]
        
        try:
            sock.sendto(chunk, (ESP32_IP, ESP32_PORT))
            total_sent += len(chunk)
            packet_count += 1
            
            # Progress update every 100 packets
            if packet_count % 100 == 0:
                progress = (total_sent / len(audio_data)) * 100
                print(f"  Progress: {progress:.1f}% ({total_sent}/{len(audio_data)} bytes)")
            
            # Small delay to prevent overwhelming ESP32
            time.sleep(0.005)  # 5ms delay between packets
            
        except socket.error as e:
            print(f"\nSocket error: {e}")
            break
    
    end_time = time.time()
    
    print("=" * 50)
    print(f"\nTransfer complete!")
    print(f"  Total packets sent: {packet_count}")
    print(f"  Total bytes sent: {total_sent}")
    print(f"  Transfer time: {end_time - start_time:.2f} seconds")
    print(f"  Transfer rate: {total_sent / (end_time - start_time) / 1024:.1f} KB/s")
    
    # Send a few empty packets to signal end (optional)
    print("\nSending end-of-stream signal...")
    for _ in range(5):
        sock.sendto(b"\x00" * 64, (ESP32_IP, ESP32_PORT))
        time.sleep(0.05)
    
    sock.close()
    print("\nDone! The ESP32 should now be playing the audio.")

def main():
    if len(sys.argv) < 2:
        print("Usage: python send_wav_to_esp32.py <wav_file>")
        print("\nExample:")
        print(f"  python send_wav_to_esp32.py /home/koogs/Documents/Mirror/speech-analyzer/recordings/esp32_prompted_speech_20260221_193100.wav")
        
        # List available recordings
        recordings_dir = "/home/koogs/Documents/Mirror/speech-analyzer/recordings"
        if os.path.exists(recordings_dir):
            print(f"\nAvailable recordings in {recordings_dir}:")
            wav_files = [f for f in os.listdir(recordings_dir) if f.endswith('.wav')]
            if wav_files:
                for f in sorted(wav_files)[-5:]:  # Show last 5 recordings
                    print(f"  - {f}")
            else:
                print("  (No WAV files found)")
        
        sys.exit(1)
    
    wav_path = sys.argv[1]
    send_wav_file(wav_path)

if __name__ == "__main__":
    main()
