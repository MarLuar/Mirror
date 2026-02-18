#!/usr/bin/env python3
"""
Utility script to update ESP32 Arduino code with the correct IP addresses from config.json
"""

import json
import os

def update_esp32_config():
    # Load configuration
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    with open(config_path, 'r') as f:
        config = json.load(f)

    # Get IP addresses from config
    esp32_ip = config.get("esp32", {}).get("ip_address", "192.168.50.75")
    computer_ip = config.get("esp32", {}).get("computer_ip", "192.168.50.130")
    
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
        code_content = f.readlines()

    # Process each line to update the IPs
    updated_lines = []
    for line in code_content:
        # Update ESP32's static IP line
        if 'IPAddress local_IP(' in line and '// ESP32\'s static IP' in line:
            # Extract the old IP pattern and replace with new IP
            new_line = f'IPAddress local_IP({esp32_ip.replace(".", ", ")});      // ESP32\'s static IP\n'
            updated_lines.append(new_line)
        # Update computer's IP address for UDP audio
        elif 'const char* udpAddress =' in line and '// Your laptop\'s IP address' in line:
            new_line = f'const char* udpAddress = "{computer_ip}";  // Your laptop\'s IP address\n'
            updated_lines.append(new_line)
        else:
            updated_lines.append(line)

    # Write the updated code back
    with open(esp32_code_path, 'w') as f:
        f.writelines(updated_lines)

    print(f"Updated ESP32 Arduino code:")
    print(f"  - ESP32 IP: {esp32_ip}")
    print(f"  - Computer IP: {computer_ip}")
    print(f"  - File: {esp32_code_path}")
    print("\\nNote: OLED display logic has been fixed to prevent prompt overwrites")
    print("\\nRemember to reflash your ESP32 with the updated code!")

if __name__ == "__main__":
    update_esp32_config()