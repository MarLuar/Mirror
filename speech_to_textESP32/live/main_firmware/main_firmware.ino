#include "WiFi.h"
#include "driver/i2s.h"
#include <WiFiUdp.h>
#include <IPAddress.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <esp_now.h>

// I2S Pin Definitions
#define I2S_WS      17
#define I2S_SCK     25
#define I2S_SD      16

// OLED Pin Definitions (SDA on D5, SCL on D23)
#define OLED_SDA    5
#define OLED_SCL    23
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64

// Button Pin for Camera Trigger (GPIO18)
#define TRIGGER_BUTTON 18

// WiFi Credentials
const char* ssid = "PLDTHOMEFIBR21653";
const char* password = "Aloygwapo1234@";

// Static IP Configuration
IPAddress local_IP(192, 168, 50, 75);      // ESP32's static IP
IPAddress gateway(192, 168, 50, 254);      // Router's IP
IPAddress subnet(255, 255, 255, 0);        // Subnet mask

// UDP Configuration - Target your laptop's IP address
const char* udpAddress = "192.168.50.234";  // Your laptop's IP address
const int audioPort = 1234;                 // Port for audio data
const int promptPort = 1235;                // Port for prompt data

WiFiUDP audioUdp;  // UDP for audio data
WiFiUDP promptUdp; // UDP for prompt data

// OLED Display Object
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

// Current prompt being displayed
char currentPrompt[256] = "Ready...";

// Audio Buffer
#define SAMPLES_PER_PACKET 512
int32_t audioBuffer[SAMPLES_PER_PACKET];

// ===================
// ESP-NOW Configuration
// ===================
// MAC Address of the Camera ESP32
uint8_t cameraMAC[] = {0x80, 0xF3, 0xDA, 0x62, 0x36, 0xCC};

// Message structure (must match camera_firmware)
typedef struct struct_message {
  char command[32];
  bool record;
} struct_message;

struct_message espNowMessage;

// ESP-NOW callback when data is sent
void OnDataSent(const uint8_t *mac_addr, esp_now_send_status_t status) {
  Serial.print("ESP-NOW Send Status: ");
  Serial.println(status == ESP_NOW_SEND_SUCCESS ? "Success" : "Fail");
}

void initESPNow() {
  // Initialize ESP-NOW
  if (esp_now_init() != ESP_OK) {
    Serial.println("ESP-NOW initialization failed!");
    return;
  }
  
  // Register callback for send status
  esp_now_register_send_cb(OnDataSent);
  
  // Add camera as peer
  esp_now_peer_info_t peerInfo = {};
  memcpy(peerInfo.peer_addr, cameraMAC, 6);
  peerInfo.channel = 0;
  peerInfo.encrypt = false;
  
  if (esp_now_add_peer(&peerInfo) != ESP_OK) {
    Serial.println("Failed to add camera as peer!");
    Serial.println("Make sure to update cameraMAC with the actual MAC address!");
    return;
  }
  
  Serial.println("ESP-NOW initialized successfully");
  Serial.print("Camera MAC: ");
  for (int i = 0; i < 6; i++) {
    Serial.printf("%02X", cameraMAC[i]);
    if (i < 5) Serial.print(":");
  }
  Serial.println();
}

// Send trigger to camera via ESP-NOW
void sendCameraTrigger(bool startRecording) {
  strcpy(espNowMessage.command, startRecording ? "RECORD" : "STOP");
  espNowMessage.record = startRecording;
  
  esp_err_t result = esp_now_send(cameraMAC, (uint8_t *)&espNowMessage, sizeof(espNowMessage));
  
  if (result == ESP_OK) {
    Serial.printf("Sent %s command to camera\n", startRecording ? "RECORD" : "STOP");
    
    // Show on OLED
    display.stopscroll();
    display.clearDisplay();
    display.setCursor(0, 0);
    display.println("Camera Trigger:");
    display.println(startRecording ? "RECORDING" : "STOPPED");
    display.display();
    delay(500); // Brief show
    updatePromptDisplay(); // Restore prompt
  } else {
    Serial.println("Failed to send ESP-NOW message");
  }
}

void initI2S() {
  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = 44100,
    // INMP441 works best when read in 32-bit mode
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
  Serial.println("I2S initialized in 32-bit mode");
}

void initOLED() {
  // Initialize I2C for OLED
  Wire.begin(OLED_SDA, OLED_SCL);

  // Initialize the OLED display
  if(!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println(F("SSD1306 allocation failed"));
    for(;;); // Don't proceed, loop forever
  }

  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
  display.println("ESP32 Mic Ready");
  display.display();
  delay(2000);
}

// Variables for scrolling functionality
bool isScrolling = false;
bool scrollSetupDone = false;
int scrollPosition = 0;
int maxScroll = 0;
unsigned long lastScrollTime = 0;
const int SCROLL_INTERVAL = 500; // milliseconds between scroll updates

// Function to wrap text to fit display width
void wrapText(const char* text, int16_t x, int16_t y, int16_t* finalY) {
  int16_t cursor_x = x, cursor_y = y;
  int16_t char_width = 6, char_height = 8;
  int16_t max_width = SCREEN_WIDTH;

  int len = strlen(text);
  int word_start = 0;

  for (int i = 0; i <= len; i++) {
    char c = (i < len) ? text[i] : ' '; // Treat end as space to flush last word

    if (c == ' ' || c == '\n' || i == len) {
      // Calculate word width
      int word_len = i - word_start;
      int word_width = word_len * char_width;

      // Check if adding this word exceeds line width
      if (cursor_x + word_width > max_width && cursor_x != x) {
        // Move to next line
        cursor_y += char_height;
        cursor_x = x;
      }

      // Print the word
      for (int j = word_start; j < i; j++) {
        display.setCursor(cursor_x, cursor_y);
        display.write(text[j]);
        cursor_x += char_width;
      }

      if (c == '\n') {
        cursor_y += char_height;
        cursor_x = x;
      } else if (c == ' ') {
        display.setCursor(cursor_x, cursor_y);
        display.write(' ');
        cursor_x += char_width;
      }

      word_start = i + 1;
    }
  }

  *finalY = cursor_y + char_height;
}

void updatePromptDisplay() {
  // Stop any existing scrolling
  display.stopscroll();

  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);

  // Calculate the total height needed for the text by wrapping it
  // We'll use a temporary calculation to determine if scrolling is needed
  int16_t totalTextHeight = calculateTextHeight(currentPrompt);

  // If text height exceeds screen height, enable vertical scrolling
  if (totalTextHeight > SCREEN_HEIGHT) {
    isScrolling = true;
    scrollSetupDone = false;
    scrollPosition = 0;
    maxScroll = totalTextHeight - SCREEN_HEIGHT + 20; // Extra space for smooth scrolling
    lastScrollTime = millis();

    // For now, just display the first portion of the text
    // The actual scrolling will happen in handleScrolling()
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    wrapTextWithScroll(currentPrompt, 0, -scrollPosition);
  } else {
    // Text fits on screen, display normally
    isScrolling = false;
    scrollSetupDone = false;
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    wrapTextWithScroll(currentPrompt, 0, 0);
  }

  display.display();
}

// Helper function to calculate text height without drawing
int16_t calculateTextHeight(const char* text) {
  int16_t cursor_x = 0, cursor_y = 0;
  int16_t char_width = 6, char_height = 8;
  int16_t max_width = SCREEN_WIDTH;

  int len = strlen(text);
  int word_start = 0;

  for (int i = 0; i <= len; i++) {
    char c = (i < len) ? text[i] : ' '; // Treat end as space to flush last word

    if (c == ' ' || c == '\n' || i == len) {
      // Calculate word width
      int word_len = i - word_start;
      int word_width = word_len * char_width;

      // Check if adding this word exceeds line width
      if (cursor_x + word_width > max_width && cursor_x != 0) {
        // Move to next line
        cursor_y += char_height;
        cursor_x = 0;
      }

      // Account for the word characters
      for (int j = word_start; j < i; j++) {
        cursor_x += char_width;
      }

      if (c == '\n') {
        cursor_y += char_height;
        cursor_x = 0;
      } else if (c == ' ') {
        cursor_x += char_width;
      }

      word_start = i + 1;
    }
  }

  return cursor_y + char_height;
}

// Modified wrapText function for scrolling display
void wrapTextWithScroll(const char* text, int16_t x, int16_t y_offset) {
  int16_t cursor_x = x, cursor_y = y_offset;
  int16_t char_width = 6, char_height = 8;
  int16_t max_width = SCREEN_WIDTH;
  int16_t max_visible_y = SCREEN_HEIGHT; // Only draw within visible area

  int len = strlen(text);
  int word_start = 0;

  for (int i = 0; i <= len; i++) {
    char c = (i < len) ? text[i] : ' '; // Treat end as space to flush last word

    if (c == ' ' || c == '\n' || i == len) {
      // Calculate word width
      int word_len = i - word_start;
      int word_width = word_len * char_width;

      // Check if adding this word exceeds line width
      if (cursor_x + word_width > max_width && cursor_x != x) {
        // Move to next line
        cursor_y += char_height;
        cursor_x = x;
      }

      // Print the word if it's within the visible area
      for (int j = word_start; j < i; j++) {
        // Only draw if the character is within the visible display area
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
        // Only draw space if it's within the visible area
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

// Function to handle continuous scrolling in the main loop
void handleScrolling() {
  if (isScrolling) {
    unsigned long currentTime = millis();

    // Update scroll position periodically
    if (currentTime - lastScrollTime > SCROLL_INTERVAL) {
      scrollPosition += 1; // Scroll by 1 pixel (slower for better readability)

      // Reset scroll position if we've scrolled all the way
      if (scrollPosition > maxScroll) {
        scrollPosition = 0;
      }

      lastScrollTime = currentTime;

      // Redraw the scrolling text
      display.clearDisplay();
      display.setTextSize(1);
      display.setTextColor(SSD1306_WHITE);

      // Display text at the current scroll position
      wrapTextWithScroll(currentPrompt, 0, -scrollPosition);

      display.display();
    }
  }
}

void setup() {
  Serial.begin(115200);

  // Initialize OLED first
  initOLED();

  // Configure static IP
  if (!WiFi.config(local_IP, gateway, subnet)) {
    Serial.println("STA Failed to configure");
  }

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());
  
  // Print MAC address for reference
  Serial.print("This device's MAC: ");
  Serial.println(WiFi.macAddress());

  // Update OLED with connection info
  display.clearDisplay();
  display.setCursor(0, 0);
  display.println("WiFi Connected!");
  display.print("IP: ");
  display.println(WiFi.localIP());
  display.print("MAC:");
  display.println(WiFi.macAddress().substring(0, 8));
  display.println("Target: ");
  display.println(udpAddress);
  display.display();
  delay(2000);

  // Initialize UDP for audio transmission
  if (audioUdp.begin(audioPort)) {
    Serial.println("Audio UDP initialized on port " + String(audioPort));
  } else {
    Serial.println("Failed to initialize Audio UDP on port " + String(audioPort));
  }

  // Initialize UDP for prompt reception
  if (promptUdp.begin(promptPort)) {
    Serial.println("Prompt UDP initialized on port " + String(promptPort));
  } else {
    Serial.println("Failed to initialize Prompt UDP on port " + String(promptPort));
  }

  // Test connectivity to target
  Serial.println("Testing connectivity to target: " + String(udpAddress));
  audioUdp.beginPacket(udpAddress, audioPort);
  audioUdp.print("Test");
  if (audioUdp.endPacket()) {
    Serial.println("Connectivity test: SUCCESS");
  } else {
    Serial.println("Connectivity test: FAILED");
  }

  // Initialize ESP-NOW for camera control
  initESPNow();

  initI2S();
  
  // Setup button pin
  pinMode(TRIGGER_BUTTON, INPUT_PULLUP);
  
  Serial.println("\n===================================");
  Serial.println("Setup complete! Commands:");
  Serial.println("  RECORD - Start camera recording");
  Serial.println("  STOP   - Stop camera recording");
  Serial.println("  CAMMAC XX:XX:XX:XX:XX:XX - Set camera MAC");
  Serial.println("===================================");
}

// Handle serial commands including camera triggers
void handleSerialCommands() {
  if (Serial.available()) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    
    Serial.printf("Serial command received: %s\n", command.c_str());
    
    if (command.equalsIgnoreCase("RECORD") || command.equalsIgnoreCase("REC")) {
      sendCameraTrigger(true);
    }
    else if (command.equalsIgnoreCase("STOP") || command.equalsIgnoreCase("END")) {
      sendCameraTrigger(false);
    }
    else if (command.startsWith("CAMMAC ") || command.startsWith("cammac ")) {
      // Parse MAC address from command
      String macStr = command.substring(7);
      macStr.trim();
      
      // Parse XX:XX:XX:XX:XX:XX format
      int values[6];
      if (sscanf(macStr.c_str(), "%x:%x:%x:%x:%x:%x", 
                 &values[0], &values[1], &values[2], 
                 &values[3], &values[4], &values[5]) == 6) {
        for (int i = 0; i < 6; i++) {
          cameraMAC[i] = (uint8_t)values[i];
        }
        
        // Reinitialize ESP-NOW with new MAC
        esp_now_deinit();
        initESPNow();
        
        Serial.println("Camera MAC updated!");
      } else {
        Serial.println("Invalid MAC format! Use: CAMMAC XX:XX:XX:XX:XX:XX");
      }
    }
  }
}

// Check trigger button
bool lastButtonState = HIGH;
bool isRecording = false;

void checkTriggerButton() {
  bool reading = digitalRead(TRIGGER_BUTTON);
  
  // Button pressed (LOW because of pull-up)
  if (reading == LOW && lastButtonState == HIGH) {
    delay(50); // Simple debounce
    if (digitalRead(TRIGGER_BUTTON) == LOW) {
      isRecording = !isRecording;
      Serial.printf("[BUTTON GPIO18] Pressed - Sending %s\n", isRecording ? "RECORD" : "STOP");
      sendCameraTrigger(isRecording);
      delay(200); // Prevent multiple triggers
    }
  }
  
  lastButtonState = reading;
}

void loop() {
  // Handle serial commands (including camera triggers)
  handleSerialCommands();
  
  // Check trigger button (GPIO0 - boot button)
  checkTriggerButton();

  // Check for incoming prompts/messages
  int promptSize = promptUdp.parsePacket();
  if (promptSize) {
    // Read the message from the UDP packet
    memset(currentPrompt, 0, sizeof(currentPrompt));
    promptUdp.read(currentPrompt, sizeof(currentPrompt) - 1);

    // Check if this is a special command
    if (strcmp(currentPrompt, "PROCESSING_AUDIO") == 0) {
      // Show processing message
      display.stopscroll(); // Stop any scrolling
      display.clearDisplay();
      display.setCursor(0, 0);
      display.println("Processing");
      display.println("Audio...");
      display.display();
      isScrolling = false; // Stop scrolling for this message
    }
    else if (strncmp(currentPrompt, "SCORE:", 6) == 0) {
      // This is a results message in format "SCORE:value|detailed_results"
      display.stopscroll(); // Stop any scrolling
      display.clearDisplay(); // Ensure complete clearing
      isScrolling = false; // Stop scrolling for this message

      // Parse the score and detailed results
      char* scoreStr = currentPrompt + 6; // Skip "SCORE:"
      char* resultsDetail = strchr(scoreStr, '|');

      if (resultsDetail != NULL) {
        *resultsDetail = '\0'; // Null-terminate the score string
        resultsDetail++; // Move past the '|' character

        // Use smaller font for more content (if available) or position text better
        // Display average score at top
        display.setTextSize(1); // Normal size
        display.setCursor(0, 0);
        display.print("Avg: ");
        display.print(atof(scoreStr), 1); // Print the score with 1 decimal place
        display.println("/10");

        // Display detailed results in a more compact format
        // Position the detailed scores lower on the screen to use space better
        display.setCursor(0, 12); // Start at y=12 (reduced from 16)
        display.setTextSize(1); // Normal size for readability

        // Display detailed results (this could be the transcription or detailed scores)
        // For better readability, let's split the results if they're too long
        int len = strlen(resultsDetail);
        int lineCount = 0;
        int maxLines = 3; // Limit to 3 lines to fit on OLED

        for (int i = 0; i < len && lineCount < maxLines; ) {
          // Find the end of the current segment (up to 21 characters to fit better with shorter names)
          int segmentEnd = i + 21;
          if (segmentEnd > len) segmentEnd = len;

          // Try to break at a space if possible
          int breakPoint = segmentEnd;
          for (int j = segmentEnd - 1; j > i; j--) {
            if (resultsDetail[j] == ' ') {
              breakPoint = j + 1;
              break;
            }
          }

          // If no space found, just break at the character limit
          if (breakPoint == segmentEnd && segmentEnd < len) {
            breakPoint = segmentEnd;
          }

          // Temporarily null-terminate for printing
          char temp = resultsDetail[breakPoint];
          resultsDetail[breakPoint] = '\0';
          display.println(&resultsDetail[i]);
          resultsDetail[breakPoint] = temp; // Restore original character

          i = breakPoint;
          lineCount++;
          display.setCursor(0, 12 + (lineCount * 12)); // Move to next line (12 pixels per line)
        }
      } else {
        // If parsing fails, just display the whole message
        display.setTextSize(1);
        display.setCursor(0, 0);
        display.println(currentPrompt);
      }
      display.display();
    }
    // Check if this is a "HOW_TO_IMPROVE" message
    else if (strncmp(currentPrompt, "IMPROVE:", 8) == 0) {
      // This is an improvement tips message
      display.stopscroll(); // Stop any scrolling
      display.clearDisplay();
      display.setTextSize(1); // Normal size
      display.setCursor(0, 0);
      display.println("Improve:");
      isScrolling = false; // Stop scrolling for this message

      // Skip "IMPROVE:" and display the tips
      char* tips = currentPrompt + 8;
      int len = strlen(tips);
      int lineCount = 0;
      int maxLines = 3; // Limit to 3 lines to fit on OLED

      // Position improvement tips lower on the screen to use space better
      display.setCursor(0, 12); // Start at y=12 (reduced from 16)
      for (int i = 0; i < len && lineCount < maxLines; ) {
        // Find the end of the current segment (up to 21 characters to fit better with shorter names)
        int segmentEnd = i + 21;
        if (segmentEnd > len) segmentEnd = len;

        // Try to break at a space if possible
        int breakPoint = segmentEnd;
        for (int j = segmentEnd - 1; j > i; j--) {
          if (tips[j] == ' ') {
            breakPoint = j + 1;
            break;
          }
        }

        // If no space found, just break at the character limit
        if (breakPoint == segmentEnd && segmentEnd < len) {
          breakPoint = segmentEnd;
        }

        // Temporarily null-terminate for printing
        char temp = tips[breakPoint];
        tips[breakPoint] = '\0';
        display.println(&tips[i]);
        tips[breakPoint] = temp; // Restore original character

        i = breakPoint;
        lineCount++;
        display.setCursor(0, 12 + (lineCount * 12)); // Move to next line (12 pixels per line)
      }
      display.display();
    }
    else {
      // Regular prompt - update the OLED display with the new prompt
      updatePromptDisplay();
    }

    Serial.println("Received message:");
    Serial.println(currentPrompt);
  }

  // Handle continuous scrolling if needed
  handleScrolling();

  size_t bytes_read;

  // Read from I2S
  i2s_read(I2S_NUM_0, &audioBuffer, sizeof(audioBuffer), &bytes_read, portMAX_DELAY);

  int samples = bytes_read / 4;

  // PROCESS AUDIO: The "Volume Boost"
  for (int i = 0; i < samples; i++) {
    // The INMP441 sends 24-bit data. We shift it to clear the noise floor
    // and then shift it left to increase the volume.
    audioBuffer[i] >>= 13; // Remove the 8 empty bits + 6 bits of noise
    audioBuffer[i] <<= 3;  // Boost the signal significantly
  }

  // Send via UDP with error checking
  // Note: beginPacket returns 1 on success, 0 on failure
  int beginResult = audioUdp.beginPacket(udpAddress, audioPort);
  if (beginResult) {
    int writeResult = audioUdp.write((uint8_t*)audioBuffer, bytes_read);
    int endResult = audioUdp.endPacket();

    // Only increment counter if packet was sent successfully
    static int counter = 0;
    static unsigned long lastUpdate = 0;
    static unsigned long lastConnectivityCheck = 0;

    if (++counter % 100 == 0) {
      Serial.printf("Streaming... Samples: %d, Packet sent: %s\n", samples,
                   (writeResult == bytes_read && endResult) ? "YES" : "NO");

      // Update OLED display every 5 seconds if no new prompt has been received recently
      if (millis() - lastUpdate > 5000) {
        // Only update status if we're not currently showing a prompt
        if (strcmp(currentPrompt, "Ready...") == 0 && !isScrolling) {
          display.stopscroll(); // Stop any scrolling
          display.clearDisplay();
          display.setCursor(0, 0);
          display.println("Streaming...");
          display.print("Samples: ");
          display.println(samples);
          display.print("Packets: ");
          display.println(counter);
          display.display();
        }
        lastUpdate = millis();
      }

      // Periodic connectivity check every 30 seconds
      if (millis() - lastConnectivityCheck > 30000) {
        Serial.println("Periodic connectivity check...");
        // Send a small test packet to verify connectivity
        audioUdp.beginPacket(udpAddress, audioPort);
        audioUdp.print("CONNCHK");
        if (!audioUdp.endPacket()) {
          Serial.println("Connectivity check failed, reinitializing UDP...");
          audioUdp.stop();
          delay(100); // Brief pause before reinitializing
          audioUdp.begin(audioPort);
        } else {
          Serial.println("Connectivity OK");
        }
        lastConnectivityCheck = millis();
      }
    }
  } else {
    Serial.printf("Failed to begin UDP packet to %s:%d\n", udpAddress, audioPort);
    // Try to reconnect/reinitialize UDP if needed
    audioUdp.stop();
    delay(100); // Brief pause before reinitializing
    audioUdp.begin(audioPort);
  }
}
