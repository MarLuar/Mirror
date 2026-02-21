#include "WiFi.h"
#include "driver/i2s.h"
#include <WiFiUdp.h>
#include <IPAddress.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <esp_now.h>

// I2S Pin Definitions for Microphone (INMP441)
#define I2S_WS      17
#define I2S_SCK     25
#define I2S_SD      16

// I2S Pin Definitions for Speaker (MAX98357A Amplifier)
#define AMP_BCLK    27
#define AMP_LRCK    26
#define AMP_DIN     14

// OLED Pin Definitions (SDA on D5, SCL on D23)
#define OLED_SDA    5
#define OLED_SCL    23
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64

// Button Pin for Camera Trigger (GPIO18)
#define TRIGGER_BUTTON 18

// WiFi Credentials
const char* ssid = "ubuntu";
const char* password = "ubuntubuntu";

// UDP Configuration - Target your laptop's IP address
const char* udpAddress = "10.42.0.1";  // Your laptop's WiFi IP on ubuntu hotspot
const int audioPort = 1234;                 // Port for audio data (to laptop)
const int promptPort = 1235;                // Port for prompt data
const int playbackPort = 1236;              // Port for receiving playback audio

WiFiUDP audioUdp;   // UDP for audio transmission (to laptop)
WiFiUDP promptUdp;  // UDP for prompt reception
WiFiUDP playbackUdp; // UDP for receiving playback audio

// OLED Display Object
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

// Current prompt being displayed
char currentPrompt[256] = "Ready...";

// Audio Buffer for microphone
#define SAMPLES_PER_PACKET 512
int32_t micAudioBuffer[SAMPLES_PER_PACKET];

// Audio Buffer for speaker playback
#define PLAYBACK_BUFFER_SIZE 1024
static uint8_t playbackBuffer[PLAYBACK_BUFFER_SIZE];
static int16_t monoPlaybackBuffer[PLAYBACK_BUFFER_SIZE / 2];

// Playback state
volatile bool isPlaybackMode = false;
unsigned long playbackStartTime = 0;
unsigned long lastPlaybackPacketTime = 0;
unsigned long playbackPacketCount = 0;
bool pendingPlaybackSwitch = false;
unsigned long playbackSwitchTime = 0;

// Display state
bool isScrolling = false;
int scrollPosition = 0;
int maxScroll = 0;
unsigned long lastScrollTime = 0;
const int SCROLL_INTERVAL = 500;

// ===================
// ESP-NOW Configuration
// ===================
uint8_t cameraMAC[] = {0x80, 0xF3, 0xDA, 0x62, 0x36, 0xCC};

typedef struct struct_message {
  char command[32];
  bool record;
} struct_message;

struct_message espNowMessage;

void OnDataSent(const uint8_t *mac_addr, esp_now_send_status_t status) {
  Serial.print("ESP-NOW Send Status: ");
  Serial.println(status == ESP_NOW_SEND_SUCCESS ? "Success" : "Fail");
}

void initESPNow() {
  if (esp_now_init() != ESP_OK) {
    Serial.println("ESP-NOW initialization failed!");
    return;
  }
  esp_now_register_send_cb(OnDataSent);
  
  esp_now_peer_info_t peerInfo = {};
  memcpy(peerInfo.peer_addr, cameraMAC, 6);
  peerInfo.channel = 0;
  peerInfo.encrypt = false;
  
  if (esp_now_add_peer(&peerInfo) != ESP_OK) {
    Serial.println("Failed to add camera as peer!");
    return;
  }
  Serial.println("ESP-NOW initialized");
}

void sendCameraTrigger(bool startRecording) {
  strcpy(espNowMessage.command, startRecording ? "RECORD" : "STOP");
  espNowMessage.record = startRecording;
  
  esp_err_t result = esp_now_send(cameraMAC, (uint8_t *)&espNowMessage, sizeof(espNowMessage));
  
  if (result == ESP_OK) {
    Serial.printf("Sent %s to camera\n", startRecording ? "RECORD" : "STOP");
    display.stopscroll();
    display.clearDisplay();
    display.setCursor(0, 0);
    display.println("Camera:");
    display.println(startRecording ? "RECORDING" : "STOPPED");
    display.display();
    delay(500);
    updatePromptDisplay();
  }
}

// ===================
// I2S Configuration
// ===================

void initI2S_Mic() {
  // Try to uninstall if already installed (ignore error if not)
  i2s_driver_uninstall(I2S_NUM_0);
  delay(10);
  
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

  esp_err_t err = i2s_driver_install(I2S_NUM_0, &i2s_config, 0, NULL);
  if (err != ESP_OK) {
    Serial.printf("I2S MIC install failed: %d\n", err);
    return;
  }

  i2s_pin_config_t pin_config = {
    .bck_io_num = I2S_SCK,
    .ws_io_num = I2S_WS,
    .data_out_num = -1,
    .data_in_num = I2S_SD
  };

  i2s_set_pin(I2S_NUM_0, &pin_config);
  Serial.println("I2S: MIC mode OK");
}

void initI2S_Speaker() {
  // Try to uninstall if already installed (ignore error if not)
  i2s_driver_uninstall(I2S_NUM_0);
  delay(10);
  
  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
    .sample_rate = 44100,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 8,
    .dma_buf_len = 64,
    .use_apll = false,
    .tx_desc_auto_clear = true,
    .fixed_mclk = 0
  };

  esp_err_t err = i2s_driver_install(I2S_NUM_0, &i2s_config, 0, NULL);
  if (err != ESP_OK) {
    Serial.printf("I2S SPEAKER install failed: %d\n", err);
    return;
  }

  i2s_pin_config_t pin_config = {
    .bck_io_num = AMP_BCLK,
    .ws_io_num = AMP_LRCK,
    .data_out_num = AMP_DIN,
    .data_in_num = I2S_PIN_NO_CHANGE
  };

  i2s_set_pin(I2S_NUM_0, &pin_config);
  Serial.println("I2S: SPEAKER mode OK");
}

void switchToPlaybackMode() {
  if (isPlaybackMode) return;
  
  isPlaybackMode = true;
  playbackPacketCount = 0;
  
  initI2S_Speaker();
  memset(playbackBuffer, 0, sizeof(playbackBuffer));
  
  Serial.println("=== PLAYBACK MODE ===");
  
  display.stopscroll();
  display.clearDisplay();
  display.setCursor(0, 0);
  display.println("Playing Back");
  display.println("Your Speech...");
  display.display();
}

void resetDisplay() {
  // Force reset the OLED display
  display.stopscroll();
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
  display.display();
}

void switchToMicMode() {
  if (!isPlaybackMode) return;
  
  Serial.println("\n=== PLAYBACK DONE ===");
  Serial.println("Restarting ESP32...");
  
  // Show restart message on display
  display.stopscroll();
  display.clearDisplay();
  display.setCursor(0, 0);
  display.println("Playback Done!");
  display.println("Restarting...");
  display.display();
  
  delay(1000);
  
  // Restart the ESP32
  ESP.restart();
}

int convertStereoToMono(uint8_t* stereoData, int stereoLen, int16_t* monoData, int monoMaxSamples) {
  int samples = stereoLen / 4;
  if (samples > monoMaxSamples) samples = monoMaxSamples;
  
  for (int i = 0; i < samples; i++) {
    int16_t left = (int16_t)(stereoData[i * 4] | (stereoData[i * 4 + 1] << 8));
    int16_t right = (int16_t)(stereoData[i * 4 + 2] | (stereoData[i * 4 + 3] << 8));
    monoData[i] = (left + right) / 2;
  }
  return samples * 2;
}

void initOLED() {
  Wire.begin(OLED_SDA, OLED_SCL);
  if(!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("SSD1306 failed");
    for(;;);
  }
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
  display.println("ESP32 Ready");
  display.display();
  delay(2000);
}

int16_t calculateTextHeight(const char* text) {
  int16_t cursor_x = 0, cursor_y = 0;
  int16_t char_width = 6, char_height = 8;
  int16_t max_width = SCREEN_WIDTH;

  int len = strlen(text);
  int word_start = 0;

  for (int i = 0; i <= len; i++) {
    char c = (i < len) ? text[i] : ' ';
    if (c == ' ' || c == '\n' || i == len) {
      int word_len = i - word_start;
      int word_width = word_len * char_width;
      if (cursor_x + word_width > max_width && cursor_x != 0) {
        cursor_y += char_height;
        cursor_x = 0;
      }
      for (int j = word_start; j < i; j++) cursor_x += char_width;
      if (c == '\n') {
        cursor_y += char_height;
        cursor_x = 0;
      } else if (c == ' ') cursor_x += char_width;
      word_start = i + 1;
    }
  }
  return cursor_y + char_height;
}

void wrapTextWithScroll(const char* text, int16_t x, int16_t y_offset) {
  int16_t cursor_x = x, cursor_y = y_offset;
  int16_t char_width = 6, char_height = 8;
  int16_t max_width = SCREEN_WIDTH;
  int16_t max_visible_y = SCREEN_HEIGHT;

  int len = strlen(text);
  int word_start = 0;

  for (int i = 0; i <= len; i++) {
    char c = (i < len) ? text[i] : ' ';
    if (c == ' ' || c == '\n' || i == len) {
      int word_len = i - word_start;
      int word_width = word_len * char_width;
      if (cursor_x + word_width > max_width && cursor_x != x) {
        cursor_y += char_height;
        cursor_x = x;
      }
      for (int j = word_start; j < i; j++) {
        if (cursor_y >= -char_height && cursor_y < max_visible_y) {
          display.setCursor(cursor_x, cursor_y);
          display.write(text[j]);
        }
        cursor_x += char_width;
      }
      if (c == '\n') {
        cursor_y += char_height;
        cursor_x = x;
      } else if (c == ' ') {
        if (cursor_y >= -char_height && cursor_y < max_visible_y) {
          display.setCursor(cursor_x, cursor_y);
          display.write(' ');
        }
        cursor_x += char_width;
      }
      word_start = i + 1;
    }
  }
}

void updatePromptDisplay() {
  display.stopscroll();
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);

  int16_t totalTextHeight = calculateTextHeight(currentPrompt);

  if (totalTextHeight > SCREEN_HEIGHT) {
    isScrolling = true;
    scrollPosition = 0;
    maxScroll = totalTextHeight - SCREEN_HEIGHT + 20;
    lastScrollTime = millis();
    wrapTextWithScroll(currentPrompt, 0, -scrollPosition);
  } else {
    isScrolling = false;
    wrapTextWithScroll(currentPrompt, 0, 0);
  }
  display.display();
}

void handleScrolling() {
  if (isScrolling) {
    unsigned long currentTime = millis();
    if (currentTime - lastScrollTime > SCROLL_INTERVAL) {
      scrollPosition += 1;
      if (scrollPosition > maxScroll) scrollPosition = 0;
      lastScrollTime = currentTime;
      display.clearDisplay();
      display.setTextSize(1);
      display.setTextColor(SSD1306_WHITE);
      wrapTextWithScroll(currentPrompt, 0, -scrollPosition);
      display.display();
    }
  }
}

void setup() {
  Serial.begin(115200);
  
  initOLED();
  
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected");
  Serial.print("IP: ");
  Serial.println(WiFi.localIP());

  display.clearDisplay();
  display.setCursor(0, 0);
  display.println("WiFi Connected!");
  display.print("IP: ");
  display.println(WiFi.localIP());
  display.display();
  delay(2000);

  if (audioUdp.begin(audioPort)) {
    Serial.println("Audio UDP on port " + String(audioPort));
  }
  if (promptUdp.begin(promptPort)) {
    Serial.println("Prompt UDP on port " + String(promptPort));
  }
  if (playbackUdp.begin(playbackPort)) {
    Serial.println("Playback UDP on port " + String(playbackPort));
  }

  initESPNow();
  initI2S_Mic();
  
  pinMode(TRIGGER_BUTTON, INPUT_PULLUP);
  
  Serial.println("\n=== Setup Complete ===");
  Serial.println("Commands: RECORD, STOP, PLAYBACK, MIC");
}

void handleSerialCommands() {
  if (Serial.available()) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    
    if (command.equalsIgnoreCase("RECORD") || command.equalsIgnoreCase("REC")) {
      sendCameraTrigger(true);
    }
    else if (command.equalsIgnoreCase("STOP") || command.equalsIgnoreCase("END")) {
      sendCameraTrigger(false);
    }
    else if (command.equalsIgnoreCase("PLAYBACK") || command.equalsIgnoreCase("PLAY")) {
      switchToPlaybackMode();
    }
    else if (command.equalsIgnoreCase("MIC")) {
      switchToMicMode();
    }
  }
}

bool lastButtonState = HIGH;
bool isRecording = false;

void checkTriggerButton() {
  bool reading = digitalRead(TRIGGER_BUTTON);
  if (reading == LOW && lastButtonState == HIGH) {
    delay(50);
    if (digitalRead(TRIGGER_BUTTON) == LOW) {
      isRecording = !isRecording;
      sendCameraTrigger(isRecording);
      delay(200);
    }
  }
  lastButtonState = reading;
}

void handlePlaybackAudio() {
  int packetSize = playbackUdp.parsePacket();
  
  if (packetSize) {
    if (packetSize > PLAYBACK_BUFFER_SIZE) packetSize = PLAYBACK_BUFFER_SIZE;
    
    int len = playbackUdp.read(playbackBuffer, packetSize);
    
    if (len > 0) {
      lastPlaybackPacketTime = millis();
      
      // Check for commands
      if (len < 10) {
        char cmd[11] = {0};
        memcpy(cmd, playbackBuffer, min(len, 10));
        
        if (strncmp(cmd, "START", 5) == 0) {
          Serial.println("Playback START");
          playbackStartTime = millis();
          playbackPacketCount = 0;
          return;
        }
        else if (strncmp(cmd, "END", 3) == 0) {
          Serial.println("Playback END");
          switchToMicMode();
          return;
        }
      }
      
      if (playbackPacketCount == 0) {
        playbackStartTime = millis();
        Serial.println("Audio playback started");
      }
      
      playbackPacketCount++;
      
      if (playbackPacketCount % 100 == 0) {
        Serial.printf("Playback: %lu packets\n", playbackPacketCount);
      }
      
      int monoBytes = convertStereoToMono(playbackBuffer, len, monoPlaybackBuffer, PLAYBACK_BUFFER_SIZE / 2);
      
      size_t written = 0;
      esp_err_t err = i2s_write(I2S_NUM_0, monoPlaybackBuffer, monoBytes, &written, 100);
      
      if (err != ESP_OK) {
        Serial.printf("I2S write error: %d\n", err);
      }
    }
  }
  
  // Check for playback timeout (3 seconds = end of stream)
  if (isPlaybackMode && playbackPacketCount > 0 && (millis() - lastPlaybackPacketTime > 3000)) {
    Serial.println("Playback complete (timeout)");
    Serial.printf("Total packets: %lu\n", playbackPacketCount);
    switchToMicMode();
  }
}

void handleMicAudio() {
  size_t bytes_read;
  esp_err_t err = i2s_read(I2S_NUM_0, &micAudioBuffer, sizeof(micAudioBuffer), &bytes_read, portMAX_DELAY);
  
  if (err != ESP_OK) {
    static int read_errors = 0;
    if (++read_errors % 100 == 0) {
      Serial.printf("I2S read error: %d\n", err);
    }
    return;
  }
  
  if (bytes_read == 0) {
    static int zero_reads = 0;
    if (++zero_reads % 100 == 0) {
      Serial.println("I2S read 0 bytes");
    }
    return;
  }

  int samples = bytes_read / 4;

  for (int i = 0; i < samples; i++) {
    micAudioBuffer[i] >>= 13;
    micAudioBuffer[i] <<= 3;
  }

  int beginResult = audioUdp.beginPacket(udpAddress, audioPort);
  if (beginResult) {
    audioUdp.write((uint8_t*)micAudioBuffer, bytes_read);
    audioUdp.endPacket();

    static int counter = 0;
    static unsigned long lastUpdate = 0;

    if (++counter % 100 == 0) {
      if (millis() - lastUpdate > 5000) {
        if (strcmp(currentPrompt, "Ready...") == 0 && !isScrolling) {
          display.stopscroll();
          display.clearDisplay();
          display.setCursor(0, 0);
          display.println("Streaming...");
          display.print("Pkts: ");
          display.println(counter);
          display.display();
        }
        lastUpdate = millis();
      }
    }
  }
}

void loop() {
  handleSerialCommands();
  checkTriggerButton();

  // Handle pending playback switch (non-blocking)
  if (pendingPlaybackSwitch) {
    unsigned long remaining = playbackSwitchTime - millis();
    if (millis() >= playbackSwitchTime) {
      Serial.println("Switching to playback now!");
      pendingPlaybackSwitch = false;
      switchToPlaybackMode();
    } else if (remaining % 1000 == 0) {  // Print countdown every second
      Serial.printf("Playback in %lu ms...\n", remaining);
    }
  }

  if (isPlaybackMode) {
    handlePlaybackAudio();
  } else {
    handleMicAudio();
    handleScrolling();
  }

  // Periodic heartbeat to check if loop is still running
  static unsigned long lastHeartbeat = 0;
  if (millis() - lastHeartbeat > 10000) {
    Serial.printf("[Heartbeat] Mode: %s, Prompt: %.20s...\n", 
      isPlaybackMode ? "PLAYBACK" : "MIC", currentPrompt);
    lastHeartbeat = millis();
  }
  
  // Check for incoming prompts (always check, regardless of mode)
  int promptSize = promptUdp.parsePacket();
  if (promptSize) {
    Serial.printf("Received prompt packet: %d bytes\n", promptSize);
    
    // Clear buffer and read new prompt
    memset(currentPrompt, 0, sizeof(currentPrompt));
    int bytesRead = promptUdp.read(currentPrompt, sizeof(currentPrompt) - 1);
    
    Serial.printf("Prompt content (%d bytes): %.50s...\n", bytesRead, currentPrompt);

    if (strcmp(currentPrompt, "PROCESSING_AUDIO") == 0) {
      Serial.println("Processing audio...");
      display.stopscroll();
      display.clearDisplay();
      display.setCursor(0, 0);
      display.println("Processing");
      display.println("Audio...");
      display.display();
      isScrolling = false;
    }
    else if (strncmp(currentPrompt, "SCORE:", 6) == 0) {
      Serial.println("SCORE received");
      display.stopscroll();
      display.clearDisplay();
      isScrolling = false;

      char* scoreStr = currentPrompt + 6;
      char* resultsDetail = strchr(scoreStr, '|');

      if (resultsDetail != NULL) {
        *resultsDetail = '\0';
        resultsDetail++;

        display.setTextSize(1);
        display.setCursor(0, 0);
        display.print("Avg: ");
        display.print(atof(scoreStr), 1);
        display.println("/10");

        display.setCursor(0, 12);
        int len = strlen(resultsDetail);
        int lineCount = 0;
        int maxLines = 3;

        for (int i = 0; i < len && lineCount < maxLines; ) {
          int segmentEnd = i + 21;
          if (segmentEnd > len) segmentEnd = len;

          int breakPoint = segmentEnd;
          for (int j = segmentEnd - 1; j > i; j--) {
            if (resultsDetail[j] == ' ') {
              breakPoint = j + 1;
              break;
            }
          }

          char temp = resultsDetail[breakPoint];
          resultsDetail[breakPoint] = '\0';
          display.println(&resultsDetail[i]);
          resultsDetail[breakPoint] = temp;

          i = breakPoint;
          lineCount++;
          display.setCursor(0, 12 + (lineCount * 12));
        }
      } else {
        display.setTextSize(1);
        display.setCursor(0, 0);
        display.println(currentPrompt);
      }
      display.display();
    }
    else if (strncmp(currentPrompt, "IMPROVE:", 8) == 0) {
      Serial.println("IMPROVE received");
      display.stopscroll();
      display.clearDisplay();
      display.setTextSize(1);
      display.setCursor(0, 0);
      display.println("Improve:");
      isScrolling = false;

      char* tips = currentPrompt + 8;
      int len = strlen(tips);
      int lineCount = 0;
      int maxLines = 3;

      display.setCursor(0, 12);
      for (int i = 0; i < len && lineCount < maxLines; ) {
        int segmentEnd = i + 21;
        if (segmentEnd > len) segmentEnd = len;

        int breakPoint = segmentEnd;
        for (int j = segmentEnd - 1; j > i; j--) {
          if (tips[j] == ' ') {
            breakPoint = j + 1;
            break;
          }
        }

        char temp = tips[breakPoint];
        tips[breakPoint] = '\0';
        display.println(&tips[i]);
        tips[breakPoint] = temp;

        i = breakPoint;
        lineCount++;
        display.setCursor(0, 12 + (lineCount * 12));
      }
      display.display();
      
      // Schedule playback switch after 5 seconds (non-blocking)
      Serial.println("Scheduling playback in 5 seconds...");
      pendingPlaybackSwitch = true;
      playbackSwitchTime = millis() + 5000;  // 5 second delay to read improvements
    }
    else {
      Serial.println("Regular prompt");
      strcpy(currentPrompt, currentPrompt);
      updatePromptDisplay();
    }
  }
  
  delay(1);
}
