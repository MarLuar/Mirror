// STEP 1: Add OLED to minimal UDP test
#include <WiFi.h>
#include <WiFiUdp.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

const char* ssid = "ubuntu";
const char* password = "ubuntubuntu";
WiFiUDP udp;
const int port = 1235;

// OLED
#define OLED_SDA 5
#define OLED_SCL 23
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

char packetBuffer[255];

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n=== STEP 1: UDP + OLED TEST ===");
  
  // Init OLED
  Wire.begin(OLED_SDA, OLED_SCL);
  if(!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("OLED failed!");
  } else {
    Serial.println("OLED OK");
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(0, 0);
    display.println("UDP + OLED Test");
    display.display();
  }
  
  // Connect WiFi
  WiFi.begin(ssid, password);
  Serial.print("WiFi connecting");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  Serial.print("IP: ");
  Serial.println(WiFi.localIP());
  
  // Update OLED
  display.println("WiFi OK");
  display.println(WiFi.localIP());
  display.display();
  
  // Start UDP
  if (udp.begin(port)) {
    Serial.printf("UDP on port %d\n", port);
  } else {
    Serial.println("UDP FAILED!");
    while(1) delay(1000);
  }
}

void loop() {
  // Check UDP
  int packetSize = udp.parsePacket();
  
  if (packetSize > 0) {
    Serial.printf("Packet received: %d bytes\n", packetSize);
    
    int len = udp.read(packetBuffer, 254);
    if (len > 0) {
      packetBuffer[len] = 0;
      Serial.printf("Data: '%s'\n", packetBuffer);
      
      // Update OLED
      display.clearDisplay();
      display.setCursor(0, 0);
      display.println("RECEIVED:");
      display.println(packetBuffer);
      display.display();
    }
  }
  
  delay(1);
}
