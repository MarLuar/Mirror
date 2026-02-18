#!/usr/bin/env python3
"""
ESP32 Audio Transmission Troubleshooting Guide
"""

def print_troubleshooting_guide():
    print("=== ESP32 Audio Transmission Troubleshooting ===\n")
    
    print("PROBLEM: ESP32 displays prompts but doesn't send audio data\n")
    
    print("POSSIBLE CAUSES AND SOLUTIONS:\n")
    
    print("1. HARDWARE CONNECTIONS")
    print("   - Verify I2S microphone is properly connected to ESP32")
    print("   - Check wiring: SD (DATA) to GPIO16, WS (LRCK) to GPIO17, SCK (BCLK) to GPIO25")
    print("   - Ensure microphone power (VCC/GND) is connected correctly")
    print("   - Check if microphone requires 3.3V power supply\n")
    
    print("2. FIRMWARE CONFIGURATION")
    print("   - Ensure you've flashed the ESP32 with updated code containing correct IP addresses")
    print("   - Run: python3 update_esp32_config_fixed.py")
    print("   - Then reflash your ESP32 with the updated firmware\n")
    
    print("3. MICROPHONE COMPATIBILITY")
    print("   - Verify your microphone model is compatible with the INMP441 settings in the code")
    print("   - The code is configured for INMP441 (I2S digital microphone)")
    print("   - If using a different model, I2S settings may need adjustment\n")
    
    print("4. SERIAL DEBUGGING")
    print("   - Connect ESP32 to computer via USB")
    print("   - Open Arduino IDE Serial Monitor (115200 baud)")
    print("   - Look for error messages or 'Streaming...' messages")
    print("   - If no streaming messages appear, microphone isn't capturing audio\n")
    
    print("5. NETWORK DIAGNOSTICS")
    print("   - Ping ESP32: ping 192.168.50.75")
    print("   - Check if firewall is blocking incoming UDP on port 1234 (should be allowed)\n")
    
    print("QUICK TEST PROCEDURE:")
    print("   1. Connect ESP32 via USB and open Serial Monitor")
    print("   2. Make sure you see 'WiFi Connected!' and 'Streaming...' messages")
    print("   3. If no 'Streaming...' messages, the issue is hardware/firmware")
    print("   4. If 'Streaming...' appears but no audio reaches computer, it's network related\n")
    
    print("TO UPDATE ESP32 FIRMWARE WITH CORRECT IPs:")
    print("   1. Run: python3 update_esp32_config_fixed.py")
    print("   2. Open Arduino IDE and upload the updated code to ESP32")
    print("   3. Restart both ESP32 and the speech analyzer application\n")
    
    print("RECOMMENDED NEXT STEPS:")
    print("   1. Check serial output from ESP32 for 'Streaming...' messages")
    print("   2. Verify hardware connections")
    print("   3. Re-flash ESP32 with updated firmware if needed")

if __name__ == "__main__":
    print_troubleshooting_guide()