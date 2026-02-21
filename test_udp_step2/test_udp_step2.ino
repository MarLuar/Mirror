// STEP 2: UDP + OLED + I2S Microphone
#include <WiFi.h>
#include <WiFiUdp.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include "driver/i2s.h"

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

// I2S Mic
#define I2S_WS 17
#define I2S_SCK 25
#define I2S_SD 16
#define SAMPLES_PER_PACKET 512
int32_t audioBuffer[SAMPLES_PER_PACKET];

char packetBuffer[255];
int udpRxCount = 0;

void initI2S() {
  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = 44100,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = (i2s_comm_format_t)(I2S_COMM_FORMAT_I2S | I2S_COMM_FORMAT_I2S_MSB),
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 8,
    .dma_buf_len = 64,
    .use_apll = false
  };
  i2s_driver_install(I2S_NUM_0, &i2s_config, 0, NULL);
  i2s_pin_config_t pin_config = {
    .bck_io_num = I2S_SCK,
    .ws_io_num = I2S_WS,
    .data_out_num = -1,
    .data_in_num = I2S_SD
  };
  i2s_set_pin(I2S_NUM_0, &pin_config);
  Serial.println("I2S OK");
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n=== STEP 2: UDP + OLED + I2S ===");
  
  // Init OLED
  Wire.begin(OLED_SDA, OLED_SCL);
  if(!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("OLED failed!");
  }
  
  // Init I2S
  initI2S();
  
  // Connect WiFi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.print("IP: ");
  Serial.println(WiFi.localIP());
  
  // Start UDP
  if (udp.begin(port)) {
    Serial.printf("UDP on port %d\n", port);
  } else {
    Serial.println("UDP FAILED!");
    while(1) delay(1000);
  }
  
  display.clearDisplay();
  display.setCursor(0,0);
  display.println("UDP+OLED+I2S");
  display.display();
  
  Serial.println("Testing - I2S blocks but UDP should still work");
}

void loop() {
  // Step 1: Check UDP (non-blocking)
  int packetSize = udp.parsePacket();
  
  if (packetSize > 0) {
    udpRxCount++;
    int len = udp.read(packetBuffer, 254);
    if (len > 0) {
      packetBuffer[len] = 0;
      Serial.printf(">>> [RX-%d] %d bytes: '%s' <<<%n", udpRxCount, packetSize, packetBuffer);
      
      // Show on OLED - don't use printf, use print
      display.clearDisplay();
      display.setCursor(0,0);
      display.print("RX #");
      display.print(udpRxCount);
      display.println(":");
      display.println(packetBuffer);
      display.display();
    }
  }
  
  // Step 2: Read I2S (BLOCKING - will wait for buffer to fill)
  size_t bytes_read;
  i2s_read(I2S_NUM_0, &audioBuffer, sizeof(audioBuffer), &bytes_read, portMAX_DELAY);
}
