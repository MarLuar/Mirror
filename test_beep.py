#!/usr/bin/env python3
"""
Ultra simple test: Send BEEP command to ESP32
Usage: python test_beep.py
"""

import socket
import time

ESP32_IP = "10.42.0.156"
ESP32_PORT = 1235

print("=" * 50)
print("ESP32 BEEP Test")
print(f"Sending to {ESP32_IP}:{ESP32_PORT}")
print("=" * 50)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Send BEEP command 5 times
for i in range(5):
    print(f"\nSending BEEP #{i+1}...")
    sock.sendto(b"BEEP", (ESP32_IP, ESP32_PORT))
    time.sleep(0.5)

sock.close()
print("\nDone! Check ESP32 Serial Monitor.")
print("You should see: [UDP] Packet received! Size: 4 bytes")
