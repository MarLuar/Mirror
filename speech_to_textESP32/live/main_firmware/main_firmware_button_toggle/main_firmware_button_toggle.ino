/*
 * ESP32 Speech Analyzer - Button Toggle Recording Version
 * 
 * Features:
 * - Press button once to start recording, press again to stop
 * - Shows 3 random prompts on OLED
 * - Triggers ESP32-CAM recording via ESP-NOW
 * - After recording: analysis + playback via speaker
 * 
 * Button: GPIO18 (press to toggle recording on/off)
 */

#include "WiFi.h"
#include "driver/i2s.h"
#include <WiFiUdp.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <esp_now.h>
#include <string.h>

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

// Long prompts pool - randomly pick 3, then auto-select 1
const char* promptPool[] = {
  // ~20 second prompts
  "Developing strong communication skills takes time and dedication. Regular practice with varied materials helps speakers become more confident.",
  "The technology industry continues to evolve at a rapid pace, bringing new opportunities and challenges to professionals around the world.",
  "Climate change represents one of the most significant challenges facing humanity today. Collective action is required.",
  "Education serves as the foundation for personal growth and societal progress. Access to quality learning resources empowers individuals.",
  "Artificial intelligence is transforming various industries, from healthcare to transportation. Understanding AI is crucial.",
  "Cultural diversity enriches our communities and workplaces. Embracing different perspectives leads to more creative solutions.",
  "Effective leadership requires empathy, vision, and the ability to inspire others. Great leaders listen actively.",
  // ~30 second prompts
  "The foundation of effective communication lies in understanding your audience and purpose. Successful speakers adapt their message, tone, and delivery to connect with listeners. Preparation involves researching your topic, organizing content logically, and anticipating questions. Confidence grows with practice.",
  "Mastering a new language requires dedication, patience, and consistent practice. Immersion experiences accelerate learning, but structured study remains important for grammar and vocabulary development. Set achievable goals and track your progress along the way.",
  "Public speaking skills benefit from understanding the fundamentals of rhetoric and audience psychology. Effective speakers establish credibility, demonstrate empathy, and support arguments with evidence. Preparation includes knowing your material and practicing aloud.",
  // ~45 second prompts
  "In today's rapidly evolving digital landscape, the ability to communicate effectively across multiple platforms has become an essential skill for professionals in every industry. Whether you are conducting a virtual meeting or delivering a presentation to stakeholders, your communication skills directly impact your success. Strong communicators understand the importance of adapting their message to different audiences and ensuring clarity in every interaction.",
  "The art of storytelling has been a fundamental part of human culture for thousands of years, and it remains one of the most powerful tools for effective communication in the modern world. Whether you are trying to persuade a client or inspire a team, framing your message within a compelling narrative structure can significantly increase its impact and create memorable experiences.",
  // ~60 second prompts
  "The journey toward becoming an exceptional communicator is a lifelong pursuit that requires dedication, self-awareness, and a genuine commitment to personal growth. Many people mistakenly believe that great speakers are born with natural talent, but the truth is that effective communication is a skill that can be developed through consistent practice and deliberate effort. The process begins with understanding your own communication style, including your strengths and areas for improvement."
};
#define NUM_PROMPTS 13

// Current selected prompt
int selectedPromptIdx = 0;  // Index in promptPool
char currentPrompt[600];    // Full text of selected prompt (increased for 60s prompts)

// Scrolling state
bool isScrolling = false;
int scrollPosition = 0;
int maxScroll = 0;
unsigned long lastScrollTime = 0;
const int SCROLL_INTERVAL = 300;

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
  
  // FIX: Add retry logic for ESP-NOW
  int retries = 3;
  for (int i = 0; i < retries; i++) {
    esp_err_t result = esp_now_send(cameraMAC, (uint8_t *)&espNowMessage, sizeof(espNowMessage));
    if (result == ESP_OK) {
      Serial.printf("Camera: %s (attempt %d/%d)\n", start ? "RECORD" : "STOP", i+1, retries);
      break;
    } else {
      Serial.printf("Camera: %s FAILED (attempt %d/%d, error: %d)\n", 
                    start ? "RECORD" : "STOP", i+1, retries, result);
      delay(50);
    }
  }
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

void showWaitingScreen() {
  // Default waiting state - ready for next recording
  display.stopscroll();
  isScrolling = false;
  
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
  display.println("=== READY ===");
  display.println("");
  display.println("Press button to");
  display.println("start recording");
  display.display();
}

void selectRandomPrompt() {
  display.stopscroll();
  isScrolling = false;
  
  // Select one random prompt from pool
  selectedPromptIdx = random(NUM_PROMPTS);
  strncpy(currentPrompt, promptPool[selectedPromptIdx], sizeof(currentPrompt) - 1);
  currentPrompt[sizeof(currentPrompt) - 1] = '\0';
  
  // Show prompt preview
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
  display.println("Read this:");
  display.println("(Press btn)");
  display.println("");
  
  // Show first part of prompt (word-wrapped)
  wrapTextWithScroll(currentPrompt, 0, 24);
  if (calculateTextHeight(currentPrompt) > 40) {
    display.setCursor(110, 56);
    display.print("...");
  }
  display.display();
}

void startScrollingPrompt() {
  // Initialize scrolling when recording starts
  int16_t totalTextHeight = calculateTextHeight(currentPrompt);
  
  if (totalTextHeight > SCREEN_HEIGHT - 16) {  // Leave room for header
    isScrolling = true;
    scrollPosition = 0;
    maxScroll = totalTextHeight - (SCREEN_HEIGHT - 16) + 10;
    lastScrollTime = millis();
  } else {
    isScrolling = false;
  }
}

void updateScrollingPrompt() {
  // Called repeatedly during recording to update scroll
  if (!isScrolling) {
    // Static display - just show text (no header)
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    wrapTextWithScroll(currentPrompt, 0, 0);
    display.display();
    return;
  }
  
  // Scrolling display
  if (millis() - lastScrollTime < SCROLL_INTERVAL) return;
  lastScrollTime = millis();
  
  scrollPosition += 1;
  if (scrollPosition > maxScroll) scrollPosition = 0;
  
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  
  wrapTextWithScroll(currentPrompt, 0, -scrollPosition);
  
  display.display();
}

void showRecordingScreen(unsigned long duration) {
  // Update scrolling prompt during recording
  updateScrollingPrompt();
}

void showProcessingScreen() {
  display.stopscroll();
  isScrolling = false;
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

void startRecording() {
  isRecording = true;
  recordingStartTime = millis();
  startScrollingPrompt();  // Initialize scrolling
  sendCameraTrigger(true);
  delay(100); // FIX: Give ESP-NOW time to send
  
  // Send START message to Python
  audioUdp.beginPacket(udpAddress, audioPort);
  audioUdp.print("START");
  audioUdp.endPacket();
  
  Serial.println("\n=================================");
  Serial.println("RECORDING STARTED");
  Serial.println("=================================");
  Serial.print("Prompt: ");
  Serial.println(currentPrompt);
}

void stopRecording() {
  isRecording = false;
  unsigned long duration = millis() - recordingStartTime;
  
  // FIX: Only send STOP to camera if recording was long enough
  if (duration > 500) { // At least 500ms
    sendCameraTrigger(false);
    delay(100); // Give ESP-NOW time to send
  }
  
  // Send STOP message to Python with duration
  audioUdp.beginPacket(udpAddress, audioPort);
  char stopMsg[32];
  snprintf(stopMsg, sizeof(stopMsg), "STOP:%lu", duration);
  audioUdp.print(stopMsg);
  audioUdp.endPacket();
  
  Serial.println("\n=================================");
  Serial.printf("RECORDING STOPPED\nDuration: %lu ms\n", duration);
  Serial.println("=================================\n");
  
  showProcessingScreen();
}

void handleButton() {
  static bool lastButtonState = HIGH;
  static unsigned long lastDebounceTime = 0;
  const unsigned long debounceDelay = 200; // 200ms debounce
  
  bool buttonState = digitalRead(BUTTON_PIN);
  
  // Button pressed (LOW because pull-up) - toggle recording
  if (buttonState == LOW && lastButtonState == HIGH) {
    if ((millis() - lastDebounceTime) > debounceDelay) {
      lastDebounceTime = millis();
      
      if (!isRecording && !isPlaybackMode) {
        // Start recording
        startRecording();
      } else if (isRecording) {
        // Stop recording
        stopRecording();
      }
    }
  }
  
  // Update scrolling prompt during recording
  if (isRecording) {
    showRecordingScreen(0);
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
          
          // Small delay to let I2S settle and buffer initial packets
          delay(200);
          
          // Clear any buffered packets to sync with fresh audio stream
          while (playbackUdp.parsePacket()) {
            playbackUdp.read(playbackBuffer, sizeof(playbackBuffer));
          }
          
          lastPlaybackPacketTime = millis();
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
  
  // Timeout after 30 seconds for longer recordings (increased from 10s)
  if (playbackPacketCount > 0 && (millis() - lastPlaybackPacketTime > 30000)) {
    Serial.println("Playback timeout");
    delay(1000);
    ESP.restart();
  }
}

void showDetailedAnalysis(const char* scoreData) {
  // Parse format: "Overall|Category1:Score1|Category2:Score2|..."
  // Example: "85|Artic:90|Pace:75|Clarity:88|Fluency:82"
  
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  
  char buffer[256];
  strncpy(buffer, scoreData, sizeof(buffer) - 1);
  buffer[sizeof(buffer) - 1] = '\0';
  
  // Parse tokens separated by '|'
  char* tokens[10];  // Max 10 categories
  int tokenCount = 0;
  char* token = strtok(buffer, "|");
  while (token != NULL && tokenCount < 10) {
    tokens[tokenCount++] = token;
    token = strtok(NULL, "|");
  }
  
  int yPos = 0;
  int lineHeight = 9;
  
  // First token is overall score - display prominently
  if (tokenCount > 0) {
    display.setCursor(0, yPos);
    display.print("OVERALL:");
    display.print(tokens[0]);
    display.println("/10");
    yPos += lineHeight;
    
    // Draw separator line
    display.drawLine(0, yPos - 2, 127, yPos - 2, SSD1306_WHITE);
  }
  
  // Display categories (2 per row to save space)
  for (int i = 1; i < tokenCount && yPos < 56; i++) {
    char* catToken = tokens[i];
    char* colon = strchr(catToken, ':');
    
    if (colon != NULL) {
      *colon = '\0';
      char* category = catToken;
      char* score = colon + 1;
      
      // Truncate category names to fit
      char catShort[7];
      strncpy(catShort, category, 6);
      catShort[6] = '\0';
      
      // Two columns: col 0 at x=0, col 1 at x=64
      int xPos = ((i - 1) % 2 == 0) ? 0 : 64;
      if ((i - 1) % 2 == 0 && i > 1) {
        yPos += lineHeight;  // New row
      }
      
      display.setCursor(xPos, yPos);
      display.print(catShort);
      display.print(":");
      display.print(score);
    }
  }
  
  // Draw progress bar at bottom for overall score (scale of 10)
  if (tokenCount > 0) {
    int overall = atoi(tokens[0]);
    int barWidth = (overall * 128) / 10;  // Scale of 10, not 100
    if (barWidth > 128) barWidth = 128;   // Cap at max width
    display.fillRect(0, 60, barWidth, 4, SSD1306_WHITE);
    display.drawRect(0, 60, 128, 4, SSD1306_WHITE);
  }
  
  display.display();
}

void handlePrompts() {
  int packetSize = promptUdp.parsePacket();
  if (!packetSize) return;
  
  char msg[256];
  int len = promptUdp.read(msg, sizeof(msg) - 1);
  msg[len] = '\0';
  
  Serial.printf("Prompt: %s\n", msg);
  
  if (strncmp(msg, "SCORE:", 6) == 0) {
    // Show detailed analysis
    showDetailedAnalysis(msg + 6);
  }
  else if (strncmp(msg, "IMPROVE:", 8) == 0) {
    // Show improvement with word wrapping
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(0, 0);
    display.println("Feedback:");
    
    // Word wrap the improvement message
    const char* text = msg + 8;
    int len = strlen(text);
    int charIdx = 0;
    int yPos = 16;
    const int charsPerLine = 21;
    const int maxLines = 5;
    int lineCount = 0;
    
    while (charIdx < len && lineCount < maxLines && yPos < 56) {
      char lineBuf[22];
      int remaining = len - charIdx;
      int toCopy = (remaining < charsPerLine) ? remaining : charsPerLine;
      
      // Try to break at space if possible
      if (toCopy < remaining) {
        for (int i = toCopy; i > 0; i--) {
          if (text[charIdx + i] == ' ') {
            toCopy = i;
            break;
          }
        }
      }
      
      strncpy(lineBuf, &text[charIdx], toCopy);
      lineBuf[toCopy] = '\0';
      
      display.setCursor(0, yPos);
      display.print(lineBuf);
      
      charIdx += toCopy;
      if (text[charIdx] == ' ') charIdx++; // Skip space
      yPos += 9;
      lineCount++;
    }
    
    display.display();
    
    delay(5000); // Show for 5 seconds
    
    isPlaybackMode = true;
    initI2S_Speaker();
    
    display.clearDisplay();
    display.setCursor(0, 0);
    display.println("Playing Back...");
    display.display();
  }
  else if (strncmp(msg, "DOWNLOAD:", 9) == 0) {
    // Show download progress
    const char* progress = msg + 9;

    display.stopscroll();
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(0, 0);
    display.println("Downloading");
    display.println("Video...");

    // Parse percentage if available
    int percent = atoi(progress);
    if (percent >= 0 && percent <= 100) {
      display.setCursor(0, 30);
      display.setTextSize(2);
      display.printf("%d%%", percent);

      // Progress bar
      int barWidth = (percent * 128) / 100;
      display.fillRect(0, 55, barWidth, 6, SSD1306_WHITE);
      display.drawRect(0, 55, 128, 6, SSD1306_WHITE);
    } else {
      // Show raw text (e.g., "512KB")
      display.setCursor(0, 30);
      display.setTextSize(2);
      display.print(progress);
    }
    display.display();
  }
  else if (strcmp(msg, "SHOW_PROMPTS") == 0) {
    // Select new random prompt
    selectRandomPrompt();
  }
  else if (strcmp(msg, "WAITING") == 0) {
    // Show waiting state (ready for next recording)
    showWaitingScreen();
  }
}

void setup() {
  Serial.begin(115200);
  randomSeed(millis());
  
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
  
  // Select and show random prompt
  selectRandomPrompt();
  
  Serial.println("\n=== READY ===");
  Serial.println("Press button to START recording");
  Serial.println("Press button again to STOP recording");
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
