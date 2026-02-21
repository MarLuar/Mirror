#!/usr/bin/env python3
"""
Simple test to stream a WAV file to ESP32 speaker
Usage: python test_playback.py <wav_file>
Example: python test_playback.py recordings/esp32_prompted_speech_20260221_191358.wav
"""

import socket
import wave
import time
import sys
import numpy as np

# ESP32 Configuration
ESP32_IP = "10.42.0.156"
ESP32_PORT = 1235  # Port ESP32 listens on for prompts/audio

def send_wav_to_esp32(wav_filepath):
    """Read a WAV file and stream it to ESP32 speaker"""
    
    print(f"=" * 60)
    print(f"ESP32 Audio Playback Test")
    print(f"Target: {ESP32_IP}:{ESP32_PORT}")
    print(f"File: {wav_filepath}")
    print(f"=" * 60)
    
    # Read the WAV file
    try:
        with wave.open(wav_filepath, 'rb') as wav_file:
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            frame_rate = wav_file.getframerate()
            n_frames = wav_file.getnframes()
            
            print(f"\n[WAV Info]")
            print(f"  Channels: {channels}")
            print(f"  Sample Width: {sample_width} bytes")
            print(f"  Frame Rate: {frame_rate} Hz")
            print(f"  Total Frames: {n_frames}")
            print(f"  Duration: {n_frames / frame_rate:.2f} seconds")
            
            # Read all audio data
            audio_data = wav_file.readframes(n_frames)
            print(f"  Data Size: {len(audio_data)} bytes")
    except Exception as e:
        print(f"[ERROR] Failed to read WAV file: {e}")
        return
    
    # Create UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # Step 1: Send IMPROVE message to trigger playback mode
    print(f"\n[Step 1] Sending IMPROVE message to ESP32...")
    improve_msg = b"IMPROVE:Playback test from WAV file"
    sock.sendto(improve_msg, (ESP32_IP, ESP32_PORT))
    print(f"  Sent: {improve_msg}")
    
    # Wait for ESP32 to enter playback mode
    print(f"  Waiting 1 second for ESP32 to prepare...")
    time.sleep(1)
    
    # Step 2: Convert audio to 16-bit if needed and stream it
    print(f"\n[Step 2] Streaming audio to ESP32...")
    
    # Convert bytes to numpy array
    if sample_width == 1:
        # 8-bit audio
        audio_array = np.frombuffer(audio_data, dtype=np.int8).astype(np.int16) * 256
    elif sample_width == 2:
        # 16-bit audio - use directly
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
    elif sample_width == 4:
        # 32-bit audio - convert to 16-bit
        audio_32bit = np.frombuffer(audio_data, dtype=np.int32)
        # Normalize to 16-bit range
        max_val = np.abs(audio_32bit).max()
        if max_val > 0:
            audio_array = (audio_32bit / max_val * 32767).astype(np.int16)
        else:
            audio_array = (audio_32bit >> 16).astype(np.int16)
    else:
        print(f"[ERROR] Unsupported sample width: {sample_width}")
        return
    
    # Convert stereo to mono if needed
    if channels == 2:
        # Reshape to separate channels and average them
        stereo = audio_array.reshape(-1, 2)
        audio_array = stereo.mean(axis=1).astype(np.int16)
        print(f"  Converted stereo to mono")
    
    print(f"  Samples to send: {len(audio_array)}")
    print(f"  Duration: {len(audio_array) / frame_rate:.2f} seconds")
    
    # Stream in chunks
    chunk_size = 1024  # samples per packet
    bytes_per_sample = 2  # 16-bit = 2 bytes
    total_samples = len(audio_array)
    samples_sent = 0
    packet_count = 0
    
    print(f"\n[Streaming] Press Ctrl+C to stop\n")
    
    try:
        for i in range(0, total_samples, chunk_size):
            chunk = audio_array[i:i+chunk_size]
            chunk_bytes = chunk.tobytes()
            packet_count += 1
            
            # Send chunk to ESP32
            sock.sendto(chunk_bytes, (ESP32_IP, ESP32_PORT))
            samples_sent += len(chunk)
            
            # Progress update every 100 packets
            if packet_count % 100 == 0:
                progress = (samples_sent / total_samples) * 100
                print(f"  Progress: {progress:.1f}% ({packet_count} packets)")
            
            # Small delay to match real-time playback
            # 1024 samples at 44100 Hz = ~23.2ms
            time.sleep(chunk_size / frame_rate * 0.9)  # Slightly faster than real-time
        
        print(f"\n[Step 3] Sending PLAYBACK_END signal...")
        sock.sendto(b"PLAYBACK_END", (ESP32_IP, ESP32_PORT))
        
        print(f"\n[Done] Sent {packet_count} packets total")
        print(f"       Audio should have played on ESP32 speaker!")
        
    except KeyboardInterrupt:
        print(f"\n\n[Interrupted] Stopping playback...")
        sock.sendto(b"PLAYBACK_END", (ESP32_IP, ESP32_PORT))
    
    sock.close()
    print(f"\nTest complete!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_playback.py <wav_file>")
        print("Example: python test_playback.py recordings/esp32_prompted_speech_20260221_191358.wav")
        sys.exit(1)
    
    wav_file = sys.argv[1]
    send_wav_to_esp32(wav_file)
