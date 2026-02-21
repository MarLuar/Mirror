// Minimal UDP receive test - no mic, just receive commands and print
#include <WiFi.h>
#include <WiFiUdp.h>

const char* ssid = "ubuntu";
const char* password = "ubuntubuntu";
WiFiUDP udp;
const int port = 1235;

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n=== Minimal UDP Test ===");
  
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  Serial.print("WiFi connected. IP: ");
  Serial.println(WiFi.localIP());
  
  if (udp.begin(port)) {
    Serial.printf("UDP listening on port %d\n", port);
  } else {
    Serial.println("UDP FAILED!");
  }
  
  Serial.println("\nWaiting for packets...");
}

void loop() {
  int packetSize = udp.parsePacket();
  if (packetSize) {
    char buffer[256];
    int len = udp.read(buffer, sizeof(buffer) - 1);
    buffer[len] = '\0';
    
    Serial.printf("[RECEIVED] %d bytes: '%s'\n", packetSize, buffer);
  }
  
  delay(1);  // Small delay
}
