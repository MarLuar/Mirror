#!/usr/bin/env python3
"""
Diagnostic tool to test ESP32 speaker playback
"""

import socket
import time
import struct
import math
import sys

ESP32_IP = "10.42.0.156"  # UPDATE THIS
ESP32_PORT = 1236

def generate_sine_wave(freq=1000, duration_sec=3, sample_rate=44100):
    """Generate a pure sine wave as 16-bit stereo PCM"""
    samples = int(sample_rate * duration_sec)
    audio_data = bytearray()
    
    for i in range(samples):
        t = i / sample_rate
        # Generate sine wave
        value = int(16000 * math.sin(2 * math.pi * freq * t))  # 16-bit range
        
        # Stereo: duplicate to left and right channels
        audio_data.extend(struct.pack('<h', value))  # Left channel
        audio_data.extend(struct.pack('<h', value))  # Right channel
    
    return bytes(audio_data)

def send_test_tone():
    """Send a generated test tone"""
    print("Generating 1000 Hz test tone (3 seconds)...")
    audio_data = generate_sine_wave(freq=1000, duration_sec=3)
    
    print(f"Generated {len(audio_data)} bytes of audio data")
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(5.0)
    
    print(f"\nConnecting to ESP32 at {ESP32_IP}:{ESP32_PORT}")
    
    # Send BEEP first
    print("Sending BEEP test...")
    sock.sendto(b"BEEP", (ESP32_IP, ESP32_PORT))
    time.sleep(0.5)
    
    # Send test tone
    print("Sending test tone...")
    chunk_size = 1024
    packet_count = 0
    
    for i in range(0, len(audio_data), chunk_size):
        chunk = audio_data[i:i+chunk_size]
        sock.sendto(chunk, (ESP32_IP, ESP32_PORT))
        packet_count += 1
        
        if packet_count % 50 == 0:
            print(f"  Sent {packet_count} packets...")
        
        time.sleep(0.004)  # 4ms delay
    
    # Send silence to end
    for _ in range(10):
        sock.sendto(b'\x00' * 64, (ESP32_IP, ESP32_PORT))
        time.sleep(0.05)
    
    sock.close()
    print(f"\n✅ Sent {packet_count} packets. Check if you hear a 1000 Hz tone!")

def send_wav_skip_header(wav_path):
    """Send WAV file but skip the header"""
    import wave
    import os
    
    if not os.path.exists(wav_path):
        print(f"File not found: {wav_path}")
        return
    
    with wave.open(wav_path, 'rb') as wav:
        channels = wav.getnchannels()
        sample_width = wav.getsampwidth()
        n_frames = wav.getnframes()
        
        print(f"WAV: {channels} ch, {sample_width} bytes, {n_frames} frames")
        
        # Read raw audio data (skips 44-byte header automatically)
        audio_data = wav.readframes(n_frames)
        print(f"Audio data: {len(audio_data)} bytes")
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    print(f"\nSending to {ESP32_IP}:{ESP32_PORT}")
    print("Skipping WAV header - sending raw audio only...")
    
    chunk_size = 1024
    packet_count = 0
    
    for i in range(0, len(audio_data), chunk_size):
        chunk = audio_data[i:i+chunk_size]
        sock.sendto(chunk, (ESP32_IP, ESP32_PORT))
        packet_count += 1
        
        if packet_count % 100 == 0:
            progress = (i / len(audio_data)) * 100
            print(f"  Progress: {progress:.1f}%")
        
        time.sleep(0.004)
    
    # End signal
    for _ in range(5):
        sock.sendto(b'\x00' * 64, (ESP32_IP, ESP32_PORT))
        time.sleep(0.05)
    
    sock.close()
    print(f"\n✅ Sent {packet_count} packets")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("ESP32 Speaker Diagnostic Tool")
        print("="*50)
        print("\nUsage:")
        print("  python diagnose_audio.py tone          # Generate test tone")
        print("  python diagnose_audio.py wav <file>    # Send WAV (skip header)")
        print("\nExamples:")
        print("  python diagnose_audio.py tone")
        print("  python diagnose_audio.py wav /path/to/recording.wav")
        sys.exit(1)
    
    if sys.argv[1] == "tone":
        send_test_tone()
    elif sys.argv[1] == "wav" and len(sys.argv) >= 3:
        send_wav_skip_header(sys.argv[2])
    else:
        print("Unknown command")
