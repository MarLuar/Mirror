#!/usr/bin/env python3
"""
Network diagnostic test for ESP32 playback
"""

import socket
import time
import subprocess
import sys

ESP32_IP = "10.42.0.156"
PLAYBACK_PORT = 1236

def test_ping():
    """Test if ESP32 is reachable"""
    print("\n=== 1. Testing Ping ===")
    result = subprocess.run(['ping', '-c', '3', ESP32_IP], 
                          capture_output=True, text=True)
    print(result.stdout)
    if result.returncode == 0:
        print("✅ ESP32 is reachable")
        return True
    else:
        print("❌ Cannot ping ESP32")
        return False

def test_udp_send():
    """Test sending UDP to ESP32"""
    print("\n=== 2. Testing UDP Send ===")
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # Send multiple test packets
    for i in range(5):
        try:
            sock.sendto(f"TEST_PACKET_{i}".encode(), (ESP32_IP, PLAYBACK_PORT))
            print(f"  Sent packet {i+1}")
            time.sleep(0.1)
        except Exception as e:
            print(f"  Error: {e}")
    
    sock.close()
    print("✅ UDP packets sent (check ESP32 Serial Monitor)")

def test_udp_receive():
    """Test receiving UDP from ESP32"""
    print("\n=== 3. Testing UDP Receive ===")
    print("Send a packet from ESP32 to this laptop...")
    print("(Use test_udp_sender.ino on ESP32 or wait)")
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", PLAYBACK_PORT))
    sock.settimeout(10.0)
    
    try:
        data, addr = sock.recvfrom(1024)
        print(f"✅ Received from {addr}: {data}")
    except socket.timeout:
        print("❌ No packet received in 10 seconds")
    
    sock.close()

def test_firewall():
    """Check if port is blocked"""
    print("\n=== 4. Checking Firewall ===")
    print(f"Port {PLAYBACK_PORT} should be open for UDP")
    
    # List listening ports
    result = subprocess.run(['ss', '-uln'], capture_output=True, text=True)
    if str(PLAYBACK_PORT) in result.stdout:
        print(f"✅ Port {PLAYBACK_PORT} is available")
    else:
        print(f"⚠️ Port {PLAYBACK_PORT} status unknown")
    
    print("\nTo allow UDP port through firewall:")
    print(f"  sudo ufw allow {PLAYBACK_PORT}/udp")
    print(f"  sudo iptables -I INPUT -p udp --dport {PLAYBACK_PORT} -j ACCEPT")

def main():
    if len(sys.argv) > 1:
        ESP32_IP = sys.argv[1]
    
    print(f"ESP32 IP: {ESP32_IP}")
    print(f"Port: {PLAYBACK_PORT}")
    
    test_ping()
    test_udp_send()
    
    print("\n" + "="*50)
    print("Check ESP32 Serial Monitor - do you see 'Packet received'?")
    print("If not, there's a network/firewall issue.")
    print("="*50)

if __name__ == "__main__":
    main()
