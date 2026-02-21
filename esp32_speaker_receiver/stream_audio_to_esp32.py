#!/usr/bin/env python3
"""
Stream WAV file to ESP32 Speaker Receiver via UDP

Usage:
    python stream_audio_to_esp32.py <wav_file>
    
Example:
    python stream_audio_to_esp32.py /home/koogs/Documents/Mirror/speech-analyzer/recordings/esp32_prompted_speech_20260221_191358.wav
"""

import socket
import sys
import time
import wave
import os
import struct

# ESP32 Configuration - UPDATE THIS WITH YOUR ESP32'S IP
ESP32_IP = "10.42.0.156"  # Change to your ESP32's actual IP address
ESP32_PORT = 1236         # Port ESP32 listens on (matches firmware)

def list_recordings():
    """List available recordings in the recordings directory"""
    recordings_dir = "/home/koogs/Documents/Mirror/speech-analyzer/recordings"
    if os.path.exists(recordings_dir):
        wav_files = [f for f in os.listdir(recordings_dir) if f.endswith('.wav')]
        if wav_files:
            print(f"\nAvailable recordings in {recordings_dir}:")
            for f in sorted(wav_files)[-10:]:  # Show last 10 recordings
                filepath = os.path.join(recordings_dir, f)
                size_mb = os.path.getsize(filepath) / (1024 * 1024)
                print(f"  - {f} ({size_mb:.2f} MB)")
            return True
    return False

def send_wav_file(wav_path):
    """Send a WAV file to ESP32 for playback"""
    
    # Check if file exists
    if not os.path.exists(wav_path):
        print(f"Error: File not found: {wav_path}")
        list_recordings()
        sys.exit(1)
    
    # Open and analyze WAV file
    print(f"\n{'='*60}")
    print(f"Opening WAV file: {wav_path}")
    print(f"{'='*60}")
    
    try:
        with wave.open(wav_path, 'rb') as wav:
            channels = wav.getnchannels()
            sample_width = wav.getsampwidth()
            frame_rate = wav.getframerate()
            n_frames = wav.getnframes()
            duration = n_frames / frame_rate
            
            print(f"\nWAV File Info:")
            print(f"  Channels: {channels} ({'Stereo' if channels == 2 else 'Mono'})")
            print(f"  Sample Width: {sample_width} bytes ({sample_width * 8}-bit)")
            print(f"  Frame Rate: {frame_rate} Hz")
            print(f"  Total Frames: {n_frames}")
            print(f"  Duration: {duration:.2f} seconds")
            
            # Warn if not 16-bit stereo 44100Hz
            if channels != 2 or sample_width != 2 or frame_rate != 44100:
                print(f"\n⚠️  Warning: Expected 16-bit stereo 44100Hz, got {sample_width*8}-bit {'Stereo' if channels==2 else 'Mono'} {frame_rate}Hz")
                print("   The ESP32 will attempt to convert if needed.")
            
            # Read all audio data
            print("\nReading audio data...")
            audio_data = wav.readframes(n_frames)
            print(f"  Read {len(audio_data)} bytes ({len(audio_data)/(1024*1024):.2f} MB)")
    except Exception as e:
        print(f"Error reading WAV file: {e}")
        sys.exit(1)
    
    # Create UDP socket
    print(f"\n{'='*60}")
    print(f"Connecting to ESP32 at {ESP32_IP}:{ESP32_PORT}")
    print(f"{'='*60}")
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(5.0)
    
    # Test connectivity first with a BEEP command
    print("\nSending test BEEP command...")
    sock.sendto(b"BEEP", (ESP32_IP, ESP32_PORT))
    time.sleep(0.5)
    
    # Send START command to signal beginning of stream
    print("Sending START command...")
    sock.sendto(b"START", (ESP32_IP, ESP32_PORT))
    time.sleep(0.1)
    
    # Send audio data in chunks
    # ESP32 expects 16-bit samples, so keep chunks even-sized
    chunk_size = 1024  # Bytes per packet (must be multiple of 4 for stereo 16-bit)
    total_sent = 0
    packet_count = 0
    
    print(f"\nSending audio data in {chunk_size}-byte chunks...")
    print(f"Estimated playback time: {duration:.2f} seconds")
    print("=" * 60)
    
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
                elapsed = time.time() - start_time
                eta = (elapsed / progress * 100) - elapsed if progress > 0 else 0
                print(f"  Progress: {progress:.1f}% | Packets: {packet_count} | ETA: {eta:.1f}s")
            
            # Small delay to prevent overwhelming ESP32 and match playback rate
            # At 44100Hz, 16-bit stereo: 1024 bytes = 256 samples = 5.8ms of audio
            # We add a small delay to let ESP32 play the audio
            time.sleep(0.004)  # 4ms delay between packets
            
        except socket.error as e:
            print(f"\nSocket error: {e}")
            break
    
    end_time = time.time()
    transfer_time = end_time - start_time
    
    print("=" * 60)
    print(f"\n✅ Transfer complete!")
    print(f"  Total packets sent: {packet_count}")
    print(f"  Total bytes sent: {total_sent}")
    print(f"  Transfer time: {transfer_time:.2f} seconds")
    print(f"  Transfer rate: {total_sent / transfer_time / 1024:.1f} KB/s")
    
    # Wait for ESP32 to finish playing
    remaining_audio_time = duration - transfer_time
    if remaining_audio_time > 0:
        print(f"\n⏳ Waiting {remaining_audio_time:.1f}s for ESP32 to finish playing...")
        time.sleep(remaining_audio_time + 0.5)  # Add 0.5s buffer
    
    # Send a few empty packets to signal end (optional)
    print("\nSending end-of-stream signal...")
    for _ in range(5):
        sock.sendto(b"\x00" * 64, (ESP32_IP, ESP32_PORT))
        time.sleep(0.05)
    
    sock.close()
    print("\n✅ Done! The ESP32 should have played the audio.")

def main():
    if len(sys.argv) < 2:
        print("Usage: python stream_audio_to_esp32.py <wav_file>")
        print("\nExample:")
        print(f"  python stream_audio_to_esp32.py /home/koogs/Documents/Mirror/speech-analyzer/recordings/esp32_prompted_speech_20260221_191358.wav")
        
        # List available recordings
        list_recordings()
        
        print(f"\n⚠️  IMPORTANT: Update ESP32_IP in this script to match your ESP32's IP!")
        print(f"   Current setting: ESP32_IP = '{ESP32_IP}'")
        sys.exit(1)
    
    wav_path = sys.argv[1]
    
    # Expand ~ to home directory
    wav_path = os.path.expanduser(wav_path)
    
    send_wav_file(wav_path)

if __name__ == "__main__":
    main()
