"""
Test script to verify the UDP prompt sending functionality
"""
import socket
import time
import json
import os

def test_udp_prompt_sending():
    print("Testing UDP prompt sending functionality...")

    # Load configuration
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    with open(config_path, 'r') as f:
        config = json.load(f)

    # Create a UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # ESP32 IP and port from config
    esp32_ip = config.get("esp32", {}).get("ip_address", "192.168.50.75")
    prompt_port = config.get("esp32", {}).get("prompt_port", 1235)
    
    # Test prompt
    test_prompt = "This is a test prompt to verify UDP communication with the ESP32 OLED display."
    
    try:
        # Send the test prompt
        sock.sendto(test_prompt.encode('utf-8'), (esp32_ip, prompt_port))
        print(f"Successfully sent prompt to ESP32: {esp32_ip}:{prompt_port}")
        print(f"Prompt: {test_prompt}")
        
        # Send a few more test prompts
        time.sleep(1)
        sock.sendto("Another test prompt".encode('utf-8'), (esp32_ip, prompt_port))
        print("Sent second test prompt")
        
        time.sleep(1)
        sock.sendto("Final test prompt".encode('utf-8'), (esp32_ip, prompt_port))
        print("Sent third test prompt")
        
    except Exception as e:
        print(f"Error sending prompt to ESP32: {e}")
        print("Make sure:")
        print("1. ESP32 is powered on and connected to WiFi")
        print("2. ESP32 IP address is correct")
        print("3. Network firewall allows UDP traffic")
    
    finally:
        sock.close()
        print("Test completed.")

if __name__ == "__main__":
    test_udp_prompt_sending()