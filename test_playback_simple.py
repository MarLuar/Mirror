#!/usr/bin/env python3
"""
Simple test for ESP32 playback
"""

import socket
import time
import wave
import os

ESP32_IP = "10.42.0.156"
PLAYBACK_PORT = 1236

def test_playback():
    # Find a recording
    recordings_dir = "/home/koogs/Documents/Mirror/speech-analyzer/recordings"
    wav_files = [f for f in os.listdir(recordings_dir) if f.endswith('.wav')]
    if not wav_files:
        print("No WAV files found!")
        return
    
    wav_path = os.path.join(recordings_dir, sorted(wav_files)[-1])
    print(f"Using: {wav_path}")
    
    with wave.open(wav_path, 'rb') as wav:
        audio_data = wav.readframes(wav.getnframes())
    
    print(f"Audio size: {len(audio_data)} bytes")
    
    # Create socket WITHOUT timeout
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # No settimeout - let it block if needed
    
    print("\n1. Sending START command 3 times...")
    for i in range(3):
        try:
            sock.sendto(b"START", (ESP32_IP, PLAYBACK_PORT))
            print(f"   START {i+1} sent")
            time.sleep(0.1)
        except Exception as e:
            print(f"   Error: {e}")
    
    print("\n2. Sending audio chunks...")
    chunk_size = 1024
    packet_count = 0
    
    try:
        for i in range(0, len(audio_data), chunk_size):
            chunk = audio_data[i:i+chunk_size]
            sock.sendto(chunk, (ESP32_IP, PLAYBACK_PORT))
            packet_count += 1
            
            if packet_count % 100 == 0:
                print(f"   Sent {packet_count} packets")
            
            time.sleep(0.005)  # 5ms delay
        
        print(f"\n✅ Sent {packet_count} packets total")
        
    except Exception as e:
        print(f"\n❌ Error during sending: {e}")
        return
    
    print("\n3. Sending END command 5 times...")
    for i in range(5):
        try:
            sock.sendto(b"END", (ESP32_IP, PLAYBACK_PORT))
            print(f"   END {i+1} sent")
            time.sleep(0.1)
        except Exception as e:
            print(f"   Error: {e}")
    
    sock.close()
    print("\n✅ Test complete!")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        ESP32_IP = sys.argv[1]
    
    print(f"ESP32 IP: {ESP32_IP}")
    print(f"Playback Port: {PLAYBACK_PORT}")
    print("\nMake sure ESP32 is in PLAYBACK mode first!")
    print("(Send IMPROVE: message or type PLAYBACK in Serial Monitor)")
    input("\nPress Enter to start test...")
    
    test_playback()
