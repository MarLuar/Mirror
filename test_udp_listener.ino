// Simple UDP listener test for ESP32

#include <WiFi.h>
#include <WiFiUdp.h>

const char* ssid = "ubuntu";
const char* password = "ubuntubuntu";

WiFiUDP udp;
const int port = 1236;

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n=== UDP Listener Test ===");
  
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  Serial.println("\nWiFi connected");
  Serial.print("IP: ");
  Serial.println(WiFi.localIP());
  
  if (udp.begin(port)) {
    Serial.println("UDP listening on port " + String(port));
  } else {
    Serial.println("Failed to start UDP!");
  }
}

void loop() {
  int packetSize = udp.parsePacket();
  
  if (packetSize) {
    Serial.print("Received packet! Size: ");
    Serial.println(packetSize);
    
    char buffer[255];
    int len = udp.read(buffer, 255);
    if (len > 0) {
      buffer[len] = 0;
      Serial.print("Data: ");
      Serial.println(buffer);
    }
    
    Serial.print("From: ");
    Serial.print(udp.remoteIP());
    Serial.print(":");
    Serial.println(udp.remotePort());
  }
  
  delay(1);
}
