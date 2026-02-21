/*
 * ESP32 UDP Debug Test - Minimal version to test UDP without I2S
 * This helps isolate whether the crash is from UDP or I2S
 */

#include <WiFi.h>
#include <WiFiUdp.h>

// WiFi Credentials
const char* ssid = "ubuntu";
const char* password = "ubuntubuntu";

WiFiUDP udp;
const int udpPort = 1235;

// Static buffer
static uint8_t buffer[512];

// Stats
unsigned long packetCount = 0;
unsigned long lastPrintTime = 0;

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n===================================");
  Serial.println("ESP32 UDP Debug Test (NO I2S)");
  Serial.println("===================================\n");
  
  // Connect to WiFi
  Serial.print("Connecting to WiFi");
  WiFi.begin(ssid, password);
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  Serial.println("\nWiFi Connected!");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());
  
  // Start UDP
  if (udp.begin(udpPort)) {
    Serial.printf("UDP listening on port %d\n", udpPort);
  } else {
    Serial.println("Failed to start UDP!");
  }
  
  Serial.println("\nReady! Send UDP packets to test...");
  Serial.println("Commands via Serial: INFO, RESET");
}

void loop() {
  // Check for UDP packets
  int packetSize = udp.parsePacket();
  
  if (packetSize) {
    // Limit read size
    int len = udp.read(buffer, min(packetSize, 512));
    
    packetCount++;
    
    // Print first few bytes as hex
    Serial.printf("[Packet %lu] Size: %d bytes, Data: ", packetCount, len);
    for (int i = 0; i < min(len, 8); i++) {
      Serial.printf("%02X ", buffer[i]);
    }
    if (len > 8) Serial.print("...");
    
    // Check if printable ASCII
    bool isText = true;
    for (int i = 0; i < min(len, 20); i++) {
      if (buffer[i] < 32 && buffer[i] != '\n' && buffer[i] != '\r') {
        isText = false;
        break;
      }
    }
    
    if (isText && len < 100) {
      Serial.print(" (Text: ");
      for (int i = 0; i < min(len, 20); i++) {
        if (buffer[i] >= 32) Serial.write(buffer[i]);
      }
      Serial.print(")");
    }
    Serial.println();
  }
  
  // Print stats every 5 seconds
  if (millis() - lastPrintTime > 5000) {
    Serial.printf("[Stats] Uptime: %lu s, Packets: %lu, Free heap: %d bytes\n", 
                  millis() / 1000, packetCount, ESP.getFreeHeap());
    lastPrintTime = millis();
  }
  
  // Handle serial commands
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    
    if (cmd.equalsIgnoreCase("INFO")) {
      Serial.printf("IP: %s, Port: %d, Packets: %lu\n", 
                    WiFi.localIP().toString().c_str(), udpPort, packetCount);
    }
    else if (cmd.equalsIgnoreCase("RESET")) {
      Serial.println("Resetting packet count...");
      packetCount = 0;
    }
  }
  
  yield();
  delay(1);
}
