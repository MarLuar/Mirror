#!/usr/bin/env python3
"""
Test ESP32 display and playback functionality
"""

import socket
import time
import sys

ESP32_IP = "10.42.0.156"  # Change to your ESP32 IP
PROMPT_PORT = 1235
PLAYBACK_PORT = 1236

def send_message(message, port):
    """Send a message to ESP32"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(message.encode(), (ESP32_IP, port))
    sock.close()
    print(f"Sent to port {port}: {message}")

def test_display():
    """Test the display messages"""
    print("\n=== Testing Display Messages ===")
    
    # Test PROCESSING message
    input("Press Enter to send 'PROCESSING_AUDIO'...")
    send_message("PROCESSING_AUDIO", PROMPT_PORT)
    time.sleep(2)
    
    # Test SCORE message
    input("Press Enter to send SCORE message...")
    send_message("SCORE:7.5|Artic:8 Pace:7 Clarity:7", PROMPT_PORT)
    time.sleep(5)
    
    # Test IMPROVE message
    input("Press Enter to send IMPROVE message...")
    send_message("IMPROVE:Speak louder Practice pacing", PROMPT_PORT)
    print("ESP32 should show improvements and switch to playback mode in 5 seconds...")
    time.sleep(6)

def test_playback_only():
    """Test only the playback functionality"""
    import wave
    import os
    
    print("\n=== Testing Playback Only ===")
    
    # Find a recording to play
    recordings_dir = "/home/koogs/Documents/Mirror/speech-analyzer/recordings"
    wav_files = [f for f in os.listdir(recordings_dir) if f.endswith('.wav')]
    
    if not wav_files:
        print("No WAV files found!")
        return
    
    wav_path = os.path.join(recordings_dir, sorted(wav_files)[-1])
    print(f"Using: {wav_path}")
    
    with wave.open(wav_path, 'rb') as wav:
        audio_data = wav.readframes(wav.getnframes())
        print(f"Loaded {len(audio_data)} bytes")
    
    input("Press Enter to send playback audio (make sure ESP32 is in PLAYBACK mode first)...")
    
    # Create socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # Send START
    print("Sending START...")
    sock.sendto(b"START", (ESP32_IP, PLAYBACK_PORT))
    time.sleep(0.5)
    
    # Send audio
    chunk_size = 1024
    packet_count = 0
    print("Sending audio...")
    
    for i in range(0, len(audio_data), chunk_size):
        chunk = audio_data[i:i+chunk_size]
        sock.sendto(chunk, (ESP32_IP, PLAYBACK_PORT))
        packet_count += 1
        if packet_count % 100 == 0:
            print(f"  Sent {packet_count} packets")
        time.sleep(0.004)
    
    print(f"Sent {packet_count} packets total")
    
    # Send END
    print("Sending END...")
    for _ in range(5):
        sock.sendto(b"END", (ESP32_IP, PLAYBACK_PORT))
        time.sleep(0.1)
    
    sock.close()
    print("Done!")

def full_test():
    """Run full test: score -> improve -> playback"""
    import wave
    import os
    
    print("\n=== Full Test: Score -> Improve -> Playback ===")
    
    # Send SCORE
    input("Press Enter to send SCORE...")
    send_message("SCORE:8.0|Artic:8 Pace:8 Clarity:8", PROMPT_PORT)
    time.sleep(3)
    
    # Send IMPROVE
    input("Press Enter to send IMPROVE (will trigger playback mode in 5s)...")
    send_message("IMPROVE:Great job Keep practicing", PROMPT_PORT)
    
    # Wait for ESP32 to switch modes
    print("Waiting 7 seconds for ESP32 to switch to playback mode...")
    time.sleep(7)
    
    # Find and send playback
    recordings_dir = "/home/koogs/Documents/Mirror/speech-analyzer/recordings"
    wav_files = [f for f in os.listdir(recordings_dir) if f.endswith('.wav')]
    
    if wav_files:
        wav_path = os.path.join(recordings_dir, sorted(wav_files)[-1])
        with wave.open(wav_path, 'rb') as wav:
            audio_data = wav.readframes(wav.getnframes())
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        print("Sending START...")
        sock.sendto(b"START", (ESP32_IP, PLAYBACK_PORT))
        time.sleep(0.3)
        
        print("Sending audio...")
        chunk_size = 1024
        for i in range(0, len(audio_data), chunk_size):
            chunk = audio_data[i:i+chunk_size]
            sock.sendto(chunk, (ESP32_IP, PLAYBACK_PORT))
            time.sleep(0.004)
        
        print("Sending END...")
        for _ in range(5):
            sock.sendto(b"END", (ESP32_IP, PLAYBACK_PORT))
            time.sleep(0.05)
        
        sock.close()
        print("Playback complete!")

def main():
    print("ESP32 Display & Playback Test")
    print("=" * 50)
    print(f"ESP32 IP: {ESP32_IP}")
    print(f"Prompt Port: {PROMPT_PORT}")
    print(f"Playback Port: {PLAYBACK_PORT}")
    print()
    
    print("Options:")
    print("  1. Test display messages only")
    print("  2. Test playback only")
    print("  3. Full test (score -> improve -> playback)")
    
    choice = input("\nEnter choice (1-3): ").strip()
    
    if choice == "1":
        test_display()
    elif choice == "2":
        test_playback_only()
    elif choice == "3":
        full_test()
    else:
        print("Invalid choice")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        ESP32_IP = sys.argv[1]
    main()
