import socket
import wave
import struct
import sys
import os

# UDP Configuration
UDP_IP = "0.0.0.0"  # Listen on all interfaces
UDP_PORT = 1234

def main():
    print(f"Listening for UDP audio on {UDP_IP}:{UDP_PORT}")
    print("Will save received audio to recorded_audio.wav")
    
    # Create UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    
    # Prepare WAV file for recording
    wav_filename = "recorded_audio.wav"
    wav_file = wave.open(wav_filename, 'wb')
    
    # Set WAV file parameters (these should match ESP32 settings)
    channels = 2  # stereo (as per ESP32 config)
    sampwidth = 2  # 16-bit (as per ESP32 config)
    framerate = 44100  # 44.1kHz (as per ESP32 config)
    
    wav_file.setnchannels(channels)
    wav_file.setsampwidth(sampwidth)
    wav_file.setframerate(framerate)
    
    print(f"Recording to {wav_filename}...")
    print("Press Ctrl+C to stop recording")
    
    try:
        received_packets = 0
        while True:
            # Receive data from UDP
            data, addr = sock.recvfrom(4096)  # Buffer size
            
            # Write raw audio data to WAV file
            wav_file.writeframes(data)
            
            # Count and report received packets periodically
            received_packets += 1
            if received_packets % 100 == 0:
                print(f"Recorded {received_packets} packets from {addr}")
                
    except KeyboardInterrupt:
        print(f"\nStopping... Received total {received_packets} packets")
    finally:
        # Close WAV file and socket
        wav_file.close()
        sock.close()
        print(f"Audio saved to {wav_filename}")
        
        # Report file size
        if os.path.exists(wav_filename):
            size = os.path.getsize(wav_filename)
            print(f"File size: {size} bytes")

if __name__ == "__main__":
    main()