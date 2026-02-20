/*
 * ESP-NOW Transmitter / Remote Control
 * 
 * This code runs on a separate ESP32 device to trigger recording
 * on the ESP32-CAM wirelessly via ESP-NOW protocol.
 * 
 * Features:
 * - Button trigger (connect button between GPIO 4 and GND)
 * - Serial commands
 * - Sends RECORD/STOP commands to ESP32-CAM
 */

#include <WiFi.h>
#include <esp_now.h>

// ===================
// Configuration
// ===================

// ESP32-CAM MAC Address (update this with your ESP32-CAM's MAC)
// You can find the MAC address in the Serial monitor when ESP32-CAM boots
uint8_t esp32CamAddress[] = {0x00, 0x00, 0x00, 0x00, 0x00, 0x00};

// Button configuration
#define BUTTON_PIN 4  // Connect button between GPIO 4 and GND

// Structure to send data - Must match receiver
typedef struct struct_message {
  char command[32];
  bool record;
} struct_message;

struct_message myData;

// ===================
// ESP-NOW Callbacks
// ===================
void OnDataSent(const uint8_t *mac_addr, esp_now_send_status_t status) {
  Serial.print("Last Packet Send Status: ");
  Serial.println(status == ESP_NOW_SEND_SUCCESS ? "Delivery Success" : "Delivery Fail");
}

// New API callback for recv (not used in transmitter but required for compatibility)
void OnDataRecv(const esp_now_recv_info *info, const uint8_t *data, int len) {
  // Not used in transmitter mode
}

// ===================
// Send Command
// ===================
void sendCommand(const char* cmd, bool record) {
  strcpy(myData.command, cmd);
  myData.record = record;
  
  esp_err_t result = esp_now_send(esp32CamAddress, (uint8_t *) &myData, sizeof(myData));
  
  if (result == ESP_OK) {
    Serial.printf("Sent command: %s (record=%d)\n", cmd, record);
  } else {
    Serial.println("Error sending command");
  }
}

// ===================
// Setup
// ===================
void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("===================================");
  Serial.println("ESP-NOW Transmitter Starting...");
  Serial.println("===================================");
  
  // Setup button
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  
  // Get this device's MAC address
  WiFi.mode(WIFI_STA);
  Serial.print("This device's MAC Address: ");
  Serial.println(WiFi.macAddress());
  Serial.println();
  Serial.println("IMPORTANT: Update the esp32CamAddress in the code");
  Serial.println("           with your ESP32-CAM's MAC address!");
  Serial.println("===================================");
  
  // Initialize ESP-NOW
  if (esp_now_init() != ESP_OK) {
    Serial.println("Error initializing ESP-NOW");
    return;
  }
  
  // Register send callback
  esp_now_register_send_cb(OnDataSent);
  
  // Register peer
  esp_now_peer_info_t peerInfo;
  memcpy(peerInfo.peer_addr, esp32CamAddress, 6);
  peerInfo.channel = 0;
  peerInfo.encrypt = false;
  
  if (esp_now_add_peer(&peerInfo) != ESP_OK) {
    Serial.println("Failed to add peer");
    return;
  }
  
  Serial.println("ESP-NOW initialized successfully");
  Serial.println();
  Serial.println("Commands:");
  Serial.println("  r, record, start  - Send RECORD command");
  Serial.println("  s, stop, end      - Send STOP command");
  Serial.println("  Press button      - Toggle record/stop");
  Serial.println("===================================");
}

// ===================
// Button Handling
// ===================
bool lastButtonState = HIGH;
bool isRecording = false;
unsigned long lastDebounceTime = 0;
const unsigned long debounceDelay = 200;

void handleButton() {
  bool reading = digitalRead(BUTTON_PIN);
  
  if (reading != lastButtonState) {
    if (millis() - lastDebounceTime > debounceDelay) {
      if (reading == LOW) {  // Button pressed (active LOW)
        isRecording = !isRecording;
        if (isRecording) {
          sendCommand("RECORD", true);
          Serial.println("Button: RECORD");
        } else {
          sendCommand("STOP", false);
          Serial.println("Button: STOP");
        }
      }
      lastDebounceTime = millis();
    }
  }
  lastButtonState = reading;
}

// ===================
// Serial Commands
// ===================
void handleSerialCommands() {
  if (Serial.available()) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    command.toLowerCase();
    
    if (command == "r" || command == "record" || command == "start") {
      isRecording = true;
      sendCommand("RECORD", true);
    }
    else if (command == "s" || command == "stop" || command == "end") {
      isRecording = false;
      sendCommand("STOP", false);
    }
    else {
      Serial.println("Unknown command. Use: r/record/start or s/stop/end");
    }
  }
}

// ===================
// Main Loop
// ===================
void loop() {
  handleButton();
  handleSerialCommands();
  delay(10);
}
