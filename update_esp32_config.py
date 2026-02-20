#!/usr/bin/env python3
"""
Utility script to update ESP32 Arduino code with the correct IP addresses from config.json
"""

import json
import os
import re

def update_esp32_config():
    # Load configuration
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    with open(config_path, 'r') as f:
        config = json.load(f)

    # Get IP addresses from config
    esp32_ip = config.get("esp32", {}).get("ip_address", "10.42.0.156")
    computer_ip = config.get("esp32", {}).get("computer_ip", "10.42.0.1")
    
    # Path to the ESP32 Arduino code
    esp32_code_path = os.path.join(
        os.path.dirname(__file__), 
        'speech_to_textESP32', 
        'live', 
        'esp32_i2s_audio_udp_hotspot', 
        'esp32_i2s_audio_udp_hotspot.ino'
    )

    # Read the current Arduino code
    with open(esp32_code_path, 'r') as f:
        code_content = f.read()

    # Update the ESP32's static IP
    updated_content = re.sub(
        r'IPAddress local_IP\([^)]+\);',
        f'IPAddress local_IP({esp32_ip.replace(".", ", ")});      // ESP32\'s static IP',
        code_content
    )

    # Update the computer's IP address for UDP audio
    updated_content = re.sub(
        r'const char\* udpAddress = "[^"]+";',
        f'const char* udpAddress = "{computer_ip}";  // Your laptop\'s IP address',
        updated_content
    )

    # Write the updated code back
    with open(esp32_code_path, 'w') as f:
        f.write(updated_content)

    print(f"Updated ESP32 Arduino code:")
    print(f"  - ESP32 IP: {esp32_ip}")
    print(f"  - Computer IP: {computer_ip}")
    print(f"  - File: {esp32_code_path}")
    print("\nRemember to reflash your ESP32 with the updated code!")

if __name__ == "__main__":
    update_esp32_config()