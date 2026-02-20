# ESP32 Configuration Instructions

## Overview
This guide explains how to properly configure and flash your ESP32 for use with the speech analyzer application.

## Prerequisites
1. Arduino IDE installed with ESP32 board support
2. Adafruit SSD1306 and GFX libraries installed
3. Your computer and ESP32 connected to the same WiFi network

## Configuration Steps

### 1. Update Configuration
Before flashing your ESP32, update the `config.json` file in the main directory with your network settings:

```json
{
  "esp32": {
    "_comment": "Using DHCP - Check Serial Monitor for actual IPs",
    "ip_address": "192.168.100.75",     // UPDATE after checking Serial Monitor
    "computer_ip": "192.168.100.128",   // Your computer's IP address
    "prompt_port": 1235,                // Port for prompt data
    "audio_port": 1234                  // Port for audio data
  }
}
```

### 2. Update ESP32 Code
Run the configuration update script to automatically update the IP addresses in the Arduino code:

```bash
python3 update_esp32_config_fixed.py
```

### 3. Flash the ESP32
1. Open the Arduino IDE
2. Navigate to `speech_to_textESP32/live/esp32_i2s_audio_udp_hotspot/esp32_i2s_audio_udp_hotspot.ino`
3. Connect your ESP32 to your computer via USB
4. Select the correct board (e.g., "ESP32 Dev Module") and COM port
5. Update the WiFi credentials in the code if needed:
   ```cpp
   const char* ssid = "YOUR_WIFI_SSID";
   const char* password = "YOUR_WIFI_PASSWORD";
   ```
6. Upload the sketch to your ESP32

### 4. Verify Connection
1. Once flashed, the ESP32 will connect to your WiFi network with the assigned static IP
2. The OLED display should show the current prompt when one is sent
3. The ESP32 will stream audio data to your computer's IP address on port 1234

## Troubleshooting

### ESP32 not connecting to WiFi
- Check that your WiFi credentials are correct in the Arduino code
- Ensure the ESP32 and your computer are on the same network
- Verify the static IP configuration doesn't conflict with other devices

### Prompt not displaying on OLED
- Verify that the ESP32 IP in config.json matches the one programmed in the Arduino code
- Check that the prompt port (1235) is accessible

### No audio data received
- Ensure the computer IP in the Arduino code matches your actual computer IP
- Check that firewall settings allow incoming UDP traffic on port 1234
- Verify the ESP32 is properly receiving and transmitting audio

## Network Configuration
The network configuration uses DHCP (automatic IP assignment):
- WiFi SSID: `ubuntu`
- WiFi Password: `ubuntubuntu`
- ESP32 Audio IP: `10.42.0.156` (check Serial Monitor)
- ESP32-CAM IP: `10.42.0.82` (check Serial Monitor)
- Computer WiFi IP: `10.42.0.1` (on ubuntu hotspot)

> **Note:** Both ESP32 devices and your laptop must be on the same 10.42.0.x network to communicate.