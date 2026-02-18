#!/usr/bin/env python3
"""
Simple UDP listener to test if ESP32 is sending audio data
"""

import socket
import time

def test_udp_listener():
    # Create UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', 1234))
    
    print("UDP Listener started on 0.0.0.0:1234")
    print("Waiting for data from ESP32...")
    print("Press Ctrl+C to stop")
    
    try:
        while True:
            data, addr = sock.recvfrom(1024)  # Buffer size is 1024 bytes
            print(f"Received {len(data)} bytes from {addr}: {data[:50]}...")
            
            # If we receive data, acknowledge it
            if data:
                print(f"Data received successfully from {addr}")
                
    except KeyboardInterrupt:
        print("\nStopping UDP listener...")
    finally:
        sock.close()

if __name__ == "__main__":
    test_udp_listener()