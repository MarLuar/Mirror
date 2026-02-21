/*
 * ESP32 Speech Analyzer - Button Hold Recording Version
 * 
 * Features:
 * - Hold button to record (duration = hold time)
 * - Shows 3 random prompts on OLED
 * - Triggers ESP32-CAM recording via ESP-NOW
 * - After recording: analysis + playback via speaker
 * 
 * Button: GPIO18 (hold to record, release to stop)
 */

#include "WiFi.h"
#include "driver/i2s.h"
#include <WiFiUdp.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <esp_now.h>

// Pin Definitions
#define I2S_WS      17   // INMP441 mic
#define I2S_SCK     25
#define I2S_SD      16
#define AMP_BCLK    27   // MAX98357A speaker
#define AMP_LRCK    26
#define AMP_DIN     14
#define OLED_SDA    5
#define OLED_SCL    23
#define BUTTON_PIN  18   // Record button

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64

// WiFi
const char* ssid = "ubuntu";
const char* password = "ubuntubuntu";
const char* udpAddress = "10.42.0.1";

// Ports
const int audioPort = 1234;
const int promptPort = 1235;
const int playbackPort = 1236;

// UDP
WiFiUDP audioUdp;
WiFiUDP promptUdp;
WiFiUDP playbackUdp;

// OLED
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

// Buffers
#define SAMPLES_PER_PACKET 512
int32_t micAudioBuffer[SAMPLES_PER_PACKET];
static uint8_t playbackBuffer[1024];
static int16_t monoPlaybackBuffer[512];

// State
volatile bool isRecording = false;
volatile bool isPlaybackMode = false;
unsigned long recordingStartTime = 0;
unsigned long playbackPacketCount = 0;
unsigned long lastPlaybackPacketTime = 0;

// 3 Random prompts pool
const char* promptPool[] = {
  "The quick brown fox jumps over the lazy dog",
  "Pack my box with five dozen liquor jugs",
  "How vexingly quick daft zebras jump",
  "Sphinx of black quartz judge my vow",
  "Two driven jocks help fax my big quiz",
  "The five boxing wizards jump quickly",
  "Jinxed wizards pluck ivy from the big quilt"
};
#define NUM_PROMPTS 7

// Current 3 prompts
char currentPrompts[3][60];
int currentPromptIndex = 0;

// ESP-NOW
uint8_t cameraMAC[] = {0x80, 0xF3, 0xDA, 0x62, 0x36, 0xCC};
typedef struct { char command[32]; bool record; } struct_message;
struct_message espNowMessage;

void OnDataSent(const uint8_t *mac, esp_now_send_status_t status) {
  Serial.println(status == ESP_NOW_SEND_SUCCESS ? "ESP-NOW: OK" : "ESP-NOW: FAIL");
}

void initESPNow() {
  if (esp_now_init() != ESP_OK) return;
  esp_now_register_send_cb(OnDataSent);
  esp_now_peer_info_t peerInfo = {};
  memcpy(peerInfo.peer_addr, cameraMAC, 6);
  peerInfo.channel = 0;
  peerInfo.encrypt = false;
  esp_now_add_peer(&peerInfo);
}

void sendCameraTrigger(bool start) {
  strcpy(espNowMessage.command, start ? "RECORD" : "STOP");
  espNowMessage.record = start;
  esp_now_send(cameraMAC, (uint8_t *)&espNowMessage, sizeof(espNowMessage));
  Serial.printf("Camera: %s\n", start ? "RECORD" : "STOP");
}

void initI2S_Mic() {
  i2s_driver_uninstall(I2S_NUM_0);
  delay(10);
  
  i2s_config_t cfg = {
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
  
  i2s_driver_install(I2S_NUM_0, &cfg, 0, NULL);
  
  i2s_pin_config_t pins = {
    .bck_io_num = I2S_SCK,
    .ws_io_num = I2S_WS,
    .data_out_num = -1,
    .data_in_num = I2S_SD
  };
  
  i2s_set_pin(I2S_NUM_0, &pins);
  Serial.println("I2S: MIC mode");
}

void initI2S_Speaker() {
  i2s_driver_uninstall(I2S_NUM_0);
  delay(10);
  
  i2s_config_t cfg = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
    .sample_rate = 44100,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 8,
    .dma_buf_len = 64,
    .use_apll = false,
    .tx_desc_auto_clear = true
  };
  
  i2s_driver_install(I2S_NUM_0, &cfg, 0, NULL);
  
  i2s_pin_config_t pins = {
    .bck_io_num = AMP_BCLK,
    .ws_io_num = AMP_LRCK,
    .data_out_num = AMP_DIN,
    .data_in_num = I2S_PIN_NO_CHANGE
  };
  
  i2s_set_pin(I2S_NUM_0, &pins);
  Serial.println("I2S: SPEAKER mode");
}

void show3Prompts() {
  // Select 3 random prompts
  int indices[3];
  for (int i = 0; i < 3; i++) {
    indices[i] = random(NUM_PROMPTS);
    // Ensure no duplicates
    for (int j = 0; j < i; j++) {
      if (indices[i] == indices[j]) {
        i--;
        break;
      }
    }
  }
  
  // Copy to current prompts
  for (int i = 0; i < 3; i++) {
    strncpy(currentPrompts[i], promptPool[indices[i]], 59);
    currentPrompts[i][59] = '\0';
  }
  currentPromptIndex = 0;
  
  // Display on OLED
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
  display.println("Choose & Speak:");
  display.println("");
  
  for (int i = 0; i < 3; i++) {
    display.print(i + 1);
    display.print(". ");
    // Truncate if too long
    char buf[22];
    strncpy(buf, currentPrompts[i], 21);
    buf[21] = '\0';
    display.println(buf);
  }
  
  display.display();
}

void showRecordingScreen(unsigned long duration) {
  display.clearDisplay();
  display.setCursor(0, 0);
  display.println("RECORDING...");
  display.println("");
  display.print("Time: ");
  display.print(duration / 1000);
  display.println("s");
  display.println("");
  display.println("Release button");
  display.println("to stop");
  display.display();
}

void showProcessingScreen() {
  display.clearDisplay();
  display.setCursor(0, 0);
  display.println("Processing...");
  display.println("");
  display.println("Analyzing");
  display.println("speech...");
  display.display();
}

void initOLED() {
  Wire.begin(OLED_SDA, OLED_SCL);
  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("OLED failed");
    for (;;);
  }
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
  display.println("ESP32 Ready");
  display.display();
  delay(1000);
}

void setup() {
  Serial.begin(115200);
  randomSeed(analogRead(0));
  
  initOLED();
  
  // Connect WiFi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi OK");
  Serial.print("IP: ");
  Serial.println(WiFi.localIP());
  
  // Init UDP
  audioUdp.begin(audioPort);
  promptUdp.begin(promptPort);
  playbackUdp.begin(playbackPort);
  
  initESPNow();
  initI2S_Mic();
  
  // Button setup
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  
  // Show initial prompts
  show3Prompts();
  
  Serial.println("\n=== READY ===");
  Serial.println("Hold button to record");
  Serial.println("Release to stop");
}

void startRecording() {
  isRecording = true;
  recordingStartTime = millis();
  sendCameraTrigger(true);
  Serial.println("=== RECORDING STARTED ===");
}

void stopRecording() {
  isRecording = false;
  unsigned long duration = millis() - recordingStartTime;
  sendCameraTrigger(false);
  Serial.printf("=== RECORDING STOPPED ===\nDuration: %lu ms\n", duration);
  
  // Send duration to Python via UDP
  audioUdp.beginPacket(udpAddress, audioPort);
  char durationMsg[32];
  snprintf(durationMsg, sizeof(durationMsg), "DURATION:%lu", duration);
  audioUdp.print(durationMsg);
  audioUdp.endPacket();
  
  showProcessingScreen();
}

void handleButton() {
  static bool lastButtonState = HIGH;
  static unsigned long buttonPressTime = 0;
  static bool wasRecording = false;
  
  bool buttonState = digitalRead(BUTTON_PIN);
  
  // Button pressed (LOW because pull-up)
  if (buttonState == LOW && lastButtonState == HIGH) {
    delay(50); // Debounce
    if (digitalRead(BUTTON_PIN) == LOW) {
      buttonPressTime = millis();
      if (!isRecording && !isPlaybackMode) {
        startRecording();
        wasRecording = true;
      }
    }
  }
  
  // Button held - update recording time on screen
  if (isRecording && buttonState == LOW) {
    unsigned long duration = millis() - recordingStartTime;
    if (duration % 500 == 0) { // Update every 500ms
      showRecordingScreen(duration);
    }
  }
  
  // Button released
  if (buttonState == HIGH && lastButtonState == LOW) {
    delay(50); // Debounce
    if (isRecording) {
      stopRecording();
      wasRecording = false;
    }
  }
  
  lastButtonState = buttonState;
}

void handleMicAudio() {
  if (!isRecording) return;
  
  size_t bytes_read;
  i2s_read(I2S_NUM_0, &micAudioBuffer, sizeof(micAudioBuffer), &bytes_read, portMAX_DELAY);
  
  if (bytes_read == 0) return;
  
  // Process audio
  int samples = bytes_read / 4;
  for (int i = 0; i < samples; i++) {
    micAudioBuffer[i] >>= 13;
    micAudioBuffer[i] <<= 3;
  }
  
  // Send to laptop
  if (audioUdp.beginPacket(udpAddress, audioPort)) {
    audioUdp.write((uint8_t*)micAudioBuffer, bytes_read);
    audioUdp.endPacket();
  }
}

void handlePlaybackAudio() {
  int packetSize = playbackUdp.parsePacket();
  
  if (packetSize) {
    if (packetSize > 1024) packetSize = 1024;
    
    int len = playbackUdp.read(playbackBuffer, packetSize);
    
    if (len > 0) {
      lastPlaybackPacketTime = millis();
      
      // Check for commands
      if (len < 10) {
        char cmd[11] = {0};
        memcpy(cmd, playbackBuffer, len);
        
        if (strncmp(cmd, "START", 5) == 0) {
          Serial.println("Playback START");
          playbackPacketCount = 0;
          
          display.clearDisplay();
          display.setCursor(0, 0);
          display.println("Playing Back...");
          display.display();
          return;
        }
        else if (strncmp(cmd, "END", 3) == 0) {
          Serial.println("Playback END");
          delay(1000);
          ESP.restart(); // Restart after playback
          return;
        }
      }
      
      playbackPacketCount++;
      
      // Convert stereo to mono and play
      int samples = len / 4;
      for (int i = 0; i < samples && i < 512; i++) {
        int16_t left = (int16_t)(playbackBuffer[i * 4] | (playbackBuffer[i * 4 + 1] << 8));
        int16_t right = (int16_t)(playbackBuffer[i * 4 + 2] | (playbackBuffer[i * 4 + 3] << 8));
        monoPlaybackBuffer[i] = (left + right) / 2;
      }
      
      size_t written;
      i2s_write(I2S_NUM_0, monoPlaybackBuffer, samples * 2, &written, 100);
    }
  }
  
  // Timeout after 3 seconds
  if (playbackPacketCount > 0 && (millis() - lastPlaybackPacketTime > 3000)) {
    Serial.println("Playback timeout");
    delay(1000);
    ESP.restart();
  }
}

void handlePrompts() {
  int packetSize = promptUdp.parsePacket();
  if (!packetSize) return;
  
  char msg[256];
  int len = promptUdp.read(msg, sizeof(msg) - 1);
  msg[len] = '\0';
  
  Serial.printf("Prompt: %s\n", msg);
  
  if (strncmp(msg, "SCORE:", 6) == 0) {
    // Show score
    display.clearDisplay();
    display.setCursor(0, 0);
    display.println("Analysis:");
    display.println("");
    display.println(msg + 6);
    display.display();
  }
  else if (strncmp(msg, "IMPROVE:", 8) == 0) {
    // Show improvement and switch to playback mode
    display.clearDisplay();
    display.setCursor(0, 0);
    display.println("Improve:");
    display.println(msg + 8);
    display.display();
    
    delay(3000); // Show for 3 seconds
    
    isPlaybackMode = true;
    initI2S_Speaker();
    
    display.clearDisplay();
    display.setCursor(0, 0);
    display.println("Playing Back...");
    display.display();
  }
  else if (strcmp(msg, "SHOW_PROMPTS") == 0) {
    // Show new 3 prompts
    show3Prompts();
  }
}

void loop() {
  handleButton();
  handlePrompts();
  
  if (isPlaybackMode) {
    handlePlaybackAudio();
  } else {
    handleMicAudio();
  }
  
  delay(1);
}
