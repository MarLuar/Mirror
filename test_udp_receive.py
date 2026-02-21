#!/usr/bin/env python3
"""
Test if UDP packets can be received from ESP32
"""

import socket

# Test receiving on the same port
PORT = 1236

print(f"Testing UDP receive on port {PORT}")
print("This will wait for any UDP packet...")

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", PORT))
sock.settimeout(10.0)

try:
    data, addr = sock.recvfrom(1024)
    print(f"\n✅ Received from {addr}: {data[:50]}...")
except socket.timeout:
    print("\n❌ Timeout - no packet received in 10 seconds")

sock.close()
