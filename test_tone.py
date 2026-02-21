#!/usr/bin/env python3
"""
Simple test: Generate a 1kHz tone and play it on ESP32 speaker
Usage: python test_tone.py
"""

import socket
import time
import numpy as np

# ESP32 Configuration
ESP32_IP = "10.42.0.156"
ESP32_PORT = 1235

def generate_and_play_tone():
    """Generate a 1kHz sine wave and play it on ESP32"""
    
    print(f"=" * 60)
    print(f"ESP32 Speaker Test - 1kHz Tone")
    print(f"Target: {ESP32_IP}:{ESP32_PORT}")
    print(f"=" * 60)
    
    # Generate 1kHz sine wave (2 seconds)
    sample_rate = 44100
    duration = 2
    frequency = 1000
    
    print(f"\n[Generating Tone]")
    print(f"  Frequency: {frequency} Hz")
    print(f"  Duration: {duration} seconds")
    print(f"  Sample Rate: {sample_rate} Hz")
    
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    tone = np.sin(2 * np.pi * frequency * t) * 16000  # 50% volume
    tone = tone.astype(np.int16)
    
    print(f"  Generated {len(tone)} samples")
    
    # Create UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # Step 1: Send IMPROVE message
    print(f"\n[Step 1] Sending IMPROVE message...")
    sock.sendto(b"IMPROVE:Test tone 1kHz", (ESP32_IP, ESP32_PORT))
    time.sleep(0.5)
    
    # Step 2: Stream the tone
    print(f"\n[Step 2] Streaming 1kHz tone to ESP32...")
    print(f"  You should hear a BEEP from the ESP32 speaker!")
    
    chunk_size = 1024
    total_samples = len(tone)
    packet_count = 0
    
    for i in range(0, total_samples, chunk_size):
        chunk = tone[i:i+chunk_size]
        chunk_bytes = chunk.tobytes()
        packet_count += 1
        
        sock.sendto(chunk_bytes, (ESP32_IP, ESP32_PORT))
        
        # Small delay for real-time playback
        time.sleep(chunk_size / sample_rate * 0.9)
    
    # Send end signal
    time.sleep(0.1)
    sock.sendto(b"PLAYBACK_END", (ESP32_IP, ESP32_PORT))
    
    sock.close()
    
    print(f"\n[Done] Sent {packet_count} packets")
    print(f"       Did you hear the 1kHz tone?")
    print(f"\nIf you heard it, the speaker works!")
    print(f"If not, check:")
    print(f"  1. ESP32 Serial Monitor for messages")
    print(f"  2. Speaker wiring")
    print(f"  3. Volume level")

if __name__ == "__main__":
    generate_and_play_tone()
