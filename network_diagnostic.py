#!/usr/bin/env python3
"""
Network diagnostic script for ESP32 connectivity
"""

import socket
import subprocess
import json
import os

def run_diagnostics():
    print("=== ESP32 Network Diagnostic ===\n")
    
    # Load configuration
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    with open(config_path, 'r') as f:
        config = json.load(f)

    esp32_ip = config.get("esp32", {}).get("ip_address", "10.42.0.156")
    computer_ip = config.get("esp32", {}).get("computer_ip", "10.42.0.1")
    
    print(f"Configuration:")
    print(f"  ESP32 IP: {esp32_ip}")
    print(f"  Computer IP: {computer_ip}")
    print()
    
    # Check if ESP32 is reachable
    print(f"Pinging ESP32 at {esp32_ip}...")
    result = subprocess.run(['ping', '-c', '3', esp32_ip], 
                          stdout=subprocess.DEVNULL, 
                          stderr=subprocess.DEVNULL)
    if result.returncode == 0:
        print("  ✓ ESP32 is reachable")
    else:
        print("  ✗ ESP32 is not reachable - check network connection")
    print()
    
    # Test UDP connectivity to ESP32 (prompt port)
    print(f"Testing UDP connectivity to ESP32 prompt port (1235)...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(5)
        
        # Send a test message to ESP32
        test_msg = b"Test prompt connectivity"
        sock.sendto(test_msg, (esp32_ip, 1235))
        print("  ✓ Successfully sent test message to ESP32 prompt port")
        sock.close()
    except Exception as e:
        print(f"  ✗ Error sending to ESP32: {e}")
    print()
    
    # Check if we're listening on audio port
    print(f"Checking if computer is listening on audio port (1234)...")
    try:
        # Try to bind to the port to see if it's available
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        test_sock.bind(('0.0.0.0', 1234))
        print("  ⚠ Port 1234 is not bound by another process")
        test_sock.close()
    except OSError as e:
        if "Address already in use" in str(e):
            print("  ✓ Port 1234 is already in use (likely by the application)")
        else:
            print(f"  ? Unexpected error checking port: {e}")
    print()
    
    print("=== Troubleshooting Tips ===")
    print("1. Make sure your ESP32 firmware has been updated with the correct IP addresses")
    print("2. Verify that the ESP32 is connected to the same WiFi network as your computer")
    print("3. Check that the ESP32 is properly configured with I2S microphone hardware")
    print("4. Ensure the microphone is physically connected and working")
    print("5. Check the serial output of the ESP32 for any error messages")
    print("6. Try restarting both the ESP32 and the application")
    print()
    print("To update ESP32 firmware with correct IPs, run:")
    print("  python3 update_esp32_config_fixed.py")

if __name__ == "__main__":
    run_diagnostics()