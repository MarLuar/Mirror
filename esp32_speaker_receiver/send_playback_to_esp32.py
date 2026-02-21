#!/usr/bin/env python3
"""
Send WAV playback to ESP32 after rating/improvements
This should be called after the analysis is complete and improvements have been sent

Usage:
    python send_playback_to_esp32.py <wav_file> [esp32_ip]
    
Example:
    python send_playback_to_esp32.py /home/koogs/Documents/Mirror/speech-analyzer/recordings/esp32_prompted_speech_20260221_191358.wav 10.42.0.156
"""

import socket
import sys
import time
import wave
import os

# ESP32 Configuration
ESP32_PORT = 1236  # Port ESP32 listens for playback audio

def send_playback(wav_path, esp32_ip, delay_before_playback=2.0):
    """Send a WAV file to ESP32 for playback after improvements"""
    
    # Check if file exists
    if not os.path.exists(wav_path):
        print(f"Error: File not found: {wav_path}")
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
            
            # Read all audio data
            print("\nReading audio data...")
            audio_data = wav.readframes(n_frames)
            print(f"  Read {len(audio_data)} bytes ({len(audio_data)/(1024*1024):.2f} MB)")
    except Exception as e:
        print(f"Error reading WAV file: {e}")
        sys.exit(1)
    
    # Create UDP socket
    print(f"\n{'='*60}")
    print(f"Sending playback to ESP32 at {esp32_ip}:{ESP32_PORT}")
    print(f"{'='*60}")
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(5.0)
    
    # Wait for ESP32 to switch to playback mode
    print(f"\nWaiting {delay_before_playback}s for ESP32 to switch to playback mode...")
    time.sleep(delay_before_playback)
    
    # Send START command
    print("Sending START command...")
    sock.sendto(b"START", (esp32_ip, ESP32_PORT))
    time.sleep(0.2)
    
    # Send audio data in chunks
    chunk_size = 1024  # Bytes per packet
    total_sent = 0
    packet_count = 0
    
    print(f"\nSending audio data in {chunk_size}-byte chunks...")
    print(f"Estimated playback time: {duration:.2f} seconds")
    print("=" * 60)
    
    start_time = time.time()
    
    for i in range(0, len(audio_data), chunk_size):
        chunk = audio_data[i:i+chunk_size]
        
        try:
            sock.sendto(chunk, (esp32_ip, ESP32_PORT))
            total_sent += len(chunk)
            packet_count += 1
            
            # Progress update every 100 packets
            if packet_count % 100 == 0:
                progress = (total_sent / len(audio_data)) * 100
                elapsed = time.time() - start_time
                eta = (elapsed / progress * 100) - elapsed if progress > 0 else 0
                print(f"  Progress: {progress:.1f}% | Packets: {packet_count} | ETA: {eta:.1f}s")
            
            # Small delay to match playback rate
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
    
    # Send END signal
    print("\nSending END signal...")
    for _ in range(5):
        sock.sendto(b"END", (esp32_ip, ESP32_PORT))
        time.sleep(0.05)
    
    sock.close()
    print("\n✅ Done! The ESP32 should have played back your speech.")

def main():
    if len(sys.argv) < 2:
        print("Usage: python send_playback_to_esp32.py <wav_file> [esp32_ip]")
        print("\nExample:")
        print(f"  python send_playback_to_esp32.py /path/to/recording.wav 10.42.0.156")
        
        # List available recordings
        recordings_dir = "/home/koogs/Documents/Mirror/speech-analyzer/recordings"
        if os.path.exists(recordings_dir):
            print(f"\nAvailable recordings in {recordings_dir}:")
            wav_files = [f for f in os.listdir(recordings_dir) if f.endswith('.wav')]
            if wav_files:
                for f in sorted(wav_files)[-5:]:
                    filepath = os.path.join(recordings_dir, f)
                    size_mb = os.path.getsize(filepath) / (1024 * 1024)
                    print(f"  - {f} ({size_mb:.2f} MB)")
        
        sys.exit(1)
    
    wav_path = os.path.expanduser(sys.argv[1])
    esp32_ip = sys.argv[2] if len(sys.argv) > 2 else "10.42.0.156"
    
    send_playback(wav_path, esp32_ip)

if __name__ == "__main__":
    main()
