import socket
import wave
import struct
import sys
import os
import time

# UDP Configuration
UDP_IP = "0.0.0.0"  # Listen on all interfaces
UDP_PORT = 1234

def main():
    print(f"Listening for UDP audio on {UDP_IP}:{UDP_PORT}")
    print("Will save received audio to recorded_audio.wav")
    print("Recording for 10 seconds...")
    
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
    
    start_time = time.time()
    received_packets = 0
    
    try:
        while time.time() - start_time < 10:  # Record for 10 seconds
            # Receive data from UDP with timeout
            sock.settimeout(1.0)  # 1 second timeout
            try:
                data, addr = sock.recvfrom(4096)  # Buffer size
                
                # Write raw audio data to WAV file
                wav_file.writeframes(data)
                
                # Count and report received packets periodically
                received_packets += 1
                if received_packets % 100 == 0:
                    elapsed = time.time() - start_time
                    print(f"[{elapsed:.1f}s] Recorded {received_packets} packets from {addr}")
                    
            except socket.timeout:
                # No data received in the last second
                elapsed = time.time() - start_time
                print(f"[{elapsed:.1f}s] No data received in last second")
                continue
                
    except KeyboardInterrupt:
        print(f"\nInterrupted by user")
    finally:
        # Close WAV file and socket
        wav_file.close()
        sock.close()
        
        # Calculate actual recording time
        actual_time = time.time() - start_time
        print(f"Recording stopped after {actual_time:.2f} seconds")
        print(f"Total packets received: {received_packets}")
        
        # Report file size
        if os.path.exists(wav_filename):
            size = os.path.getsize(wav_filename)
            print(f"Audio saved to {wav_filename}")
            print(f"File size: {size} bytes")
            
            # Calculate duration based on sample rate and file size
            samples = size / (2 * 2)  # 2 channels * 2 bytes per sample (16-bit)
            duration = samples / 44100
            print(f"Estimated audio duration: {duration:.2f} seconds")

if __name__ == "__main__":
    main()