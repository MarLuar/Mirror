// ABSOLUTE MINIMAL UDP TEST
// This sketch does NOTHING except listen for UDP and print

#include <WiFi.h>
#include <WiFiUdp.h>

const char* ssid = "ubuntu";
const char* password = "ubuntubuntu";
WiFiUDP udp;
const int port = 1235;

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n=== MINIMAL UDP TEST ===");
  Serial.println("This sketch ONLY listens for UDP packets");
  Serial.println("No I2S, no OLED, no ESP-NOW, no microphone");
  Serial.println("========================\n");
  
  // Connect WiFi
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  Serial.print("WiFi connected! IP: ");
  Serial.println(WiFi.localIP());
  
  // Start UDP
  if (udp.begin(port)) {
    Serial.printf("UDP listening on port %d\n", port);
    Serial.println("\nWaiting for packets...");
    Serial.println("Run: python3 -c \"import socket; s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.sendto(b'HELLO',('10.42.0.156',1235))\"");
    Serial.println("========================\n");
  } else {
    Serial.println("FAILED to start UDP!");
    while(1) delay(1000);
  }
}

void loop() {
  static unsigned long lastCheck = 0;
  static int checkCount = 0;
  
  // Check for UDP packet
  int packetSize = udp.parsePacket();
  checkCount++;
  
  if (packetSize) {
    char buffer[256];
    int len = udp.read(buffer, sizeof(buffer)-1);
    buffer[len] = '\0';
    
    Serial.printf("\n>>> [RECEIVED] %d bytes: '%s' <<<\n", packetSize, buffer);
    Serial.printf("     From: %s:%d\n", udp.remoteIP().toString().c_str(), udp.remotePort());
    
    // Echo back
    udp.beginPacket(udp.remoteIP(), udp.remotePort());
    udp.print("Echo: ");
    udp.print(buffer);
    udp.endPacket();
  }
  
  // Print heartbeat every 5 seconds
  if (millis() - lastCheck > 5000) {
    lastCheck = millis();
    Serial.printf("[ALIVE] Checks: %d, WiFi: %s, IP: %s\n", 
                  checkCount,
                  WiFi.status() == WL_CONNECTED ? "OK" : "DOWN",
                  WiFi.localIP().toString().c_str());
    checkCount = 0;
  }
  
  delay(1);  // Small delay
}
