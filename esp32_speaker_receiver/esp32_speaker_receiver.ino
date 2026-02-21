/*
 * ESP32 Speaker Receiver - MAX98357A Amplifier
 * Receives audio data via UDP and plays it through the amplifier
 * 
 * Hardware: ESP32 + MAX98357A I2S Amplifier
 * Wiring:
 *   MAX98357A VCC -> 3.3V
 *   MAX98357A GND -> GND
 *   MAX98357A BCLK -> GPIO 27
 *   MAX98357A LRC  -> GPIO 26
 *   MAX98357A DIN  -> GPIO 14
 *   MAX98357A SD   -> 3.3V (or GPIO for control)
 */

#include <WiFi.h>
#include <WiFiUdp.h>
#include <driver/i2s.h>

// WiFi Credentials
const char* ssid = "ubuntu";
const char* password = "ubuntubuntu";

// UDP Configuration
WiFiUDP udp;
const int udpPort = 1236;  // Port to listen for audio data (different from mic port)

// I2S Pin Definitions (MAX98357A Amplifier)
#define AMP_BCLK    27
#define AMP_LRCK    26
#define AMP_DIN     14

// Audio settings
#define SAMPLE_RATE 44100
#define BITS_PER_SAMPLE I2S_BITS_PER_SAMPLE_16BIT

// Buffer size
#define BUFFER_SIZE 1024

// Static buffer to avoid stack overflow
static uint8_t audioBuffer[BUFFER_SIZE];
static int16_t monoBuffer[BUFFER_SIZE / 2];  // For stereo to mono conversion

// Playback state
volatile bool isPlaying = false;
unsigned long playbackStartTime = 0;
unsigned long lastPacketTime = 0;
unsigned long packetCount = 0;

void initI2S() {
  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = BITS_PER_SAMPLE,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,  // Mono output
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
    Serial.println("ERROR: Failed to install I2S driver!");
    return;
  }
  
  i2s_pin_config_t pin_config = {
    .bck_io_num = AMP_BCLK,
    .ws_io_num = AMP_LRCK,
    .data_out_num = AMP_DIN,
    .data_in_num = I2S_PIN_NO_CHANGE
  };
  
  i2s_set_pin(I2S_NUM_0, &pin_config);
  Serial.println("I2S initialized for audio playback");
  Serial.printf("  BCLK: GPIO %d, LRCK: GPIO %d, DIN: GPIO %d\n", AMP_BCLK, AMP_LRCK, AMP_DIN);
}

void playBeep(int frequency, int duration_ms) {
  int samples = (SAMPLE_RATE * duration_ms) / 1000;
  int16_t buffer[64];
  
  Serial.printf("Playing beep: %d Hz for %d ms\n", frequency, duration_ms);
  
  for (int i = 0; i < samples; i += 64) {
    int chunk = min(64, samples - i);
    for (int j = 0; j < chunk; j++) {
      float t = (float)(i + j) / SAMPLE_RATE;
      buffer[j] = (int16_t)(sin(2 * PI * frequency * t) * 8000);  // Lower volume for startup beep
    }
    size_t written;
    i2s_write(I2S_NUM_0, buffer, chunk * sizeof(int16_t), &written, portMAX_DELAY);
  }
  
  // Clear the buffer to prevent clicking noise
  int16_t silence[64] = {0};
  for (int i = 0; i < 8; i++) {
    size_t written;
    i2s_write(I2S_NUM_0, silence, sizeof(silence), &written, portMAX_DELAY);
  }
}

// Convert stereo 16-bit to mono 16-bit
int convertStereoToMono(uint8_t* stereoData, int stereoLen, int16_t* monoData, int monoMaxSamples) {
  int samples = stereoLen / 4;  // 4 bytes per stereo sample (2 bytes left + 2 bytes right)
  if (samples > monoMaxSamples) {
    samples = monoMaxSamples;
  }
  
  for (int i = 0; i < samples; i++) {
    // Get left and right channels (little-endian)
    int16_t left = (int16_t)(stereoData[i * 4] | (stereoData[i * 4 + 1] << 8));
    int16_t right = (int16_t)(stereoData[i * 4 + 2] | (stereoData[i * 4 + 3] << 8));
    
    // Mix to mono (average of left and right)
    monoData[i] = (left + right) / 2;
  }
  
  return samples * 2;  // Return bytes in mono buffer
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n===================================");
  Serial.println("ESP32 Speaker Receiver");
  Serial.println("MAX98357A Amplifier Playback");
  Serial.println("===================================\n");
  
  // Initialize I2S for audio playback
  initI2S();
  
  // Play startup beep
  playBeep(1000, 200);
  delay(100);
  playBeep(1500, 200);
  
  // Connect to WiFi
  Serial.print("Connecting to WiFi");
  WiFi.begin(ssid, password);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("\nWiFi connection FAILED!");
    Serial.println("Check your WiFi credentials");
    return;
  }
  
  Serial.println("\nWiFi Connected!");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());
  Serial.print("MAC Address: ");
  Serial.println(WiFi.macAddress());
  
  // Start UDP with error checking
  if (udp.begin(udpPort)) {
    Serial.printf("UDP listening on port %d\n", udpPort);
  } else {
    Serial.println("Failed to start UDP!");
    return;
  }
  
  // Play ready beep
  delay(200);
  playBeep(2000, 300);
  
  Serial.println("\n===================================");
  Serial.println("Ready! Waiting for audio data...");
  Serial.printf("Send WAV file via UDP to port %d\n", udpPort);
  Serial.println("Commands:");
  Serial.println("  BEEP - Play test beep");
  Serial.println("  INFO - Show status");
  Serial.println("===================================\n");
}

void handleSerialCommands() {
  if (Serial.available()) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    
    if (command.equalsIgnoreCase("BEEP") || command.equalsIgnoreCase("TEST")) {
      Serial.println("Playing test beep...");
      playBeep(1000, 500);
    }
    else if (command.equalsIgnoreCase("INFO") || command.equalsIgnoreCase("STATUS")) {
      Serial.println("\n--- Status ---");
      Serial.printf("WiFi: %s\n", WiFi.status() == WL_CONNECTED ? "Connected" : "Disconnected");
      Serial.printf("IP: %s\n", WiFi.localIP().toString().c_str());
      Serial.printf("UDP Port: %d\n", udpPort);
      Serial.printf("Is Playing: %s\n", isPlaying ? "Yes" : "No");
      Serial.printf("Packet Count: %lu\n", packetCount);
      Serial.println("--------------\n");
    }
  }
}

void loop() {
  // Handle serial commands - do this frequently
  handleSerialCommands();
  
  // Feed watchdog timer
  yield();
  
  // Check WiFi connection and reconnect if needed
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi disconnected! Reconnecting...");
    WiFi.reconnect();
    delay(1000);
    return;
  }
  
  // Check for incoming UDP packets
  int packetSize = udp.parsePacket();
  
  if (packetSize) {
    // Limit packet size to prevent buffer overflow
    if (packetSize > BUFFER_SIZE) {
      packetSize = BUFFER_SIZE;
    }
    
    // Read the packet into static buffer
    int len = udp.read(audioBuffer, packetSize);
    
    if (len > 0) {
      lastPacketTime = millis();
      
      // Check for command packets (text commands start with ASCII chars)
      if (len < 10) {
        // Could be a text command
        char cmd[11] = {0};
        memcpy(cmd, audioBuffer, min(len, 10));
        
        if (strncmp(cmd, "BEEP", 4) == 0) {
          Serial.println("Received BEEP command");
          playBeep(800, 300);
          return;
        }
        else if (strncmp(cmd, "TEST", 4) == 0) {
          Serial.println("Received TEST command - connection OK!");
          return;
        }
        else if (strncmp(cmd, "START", 5) == 0) {
          Serial.println("=== Audio Playback Started ===");
          isPlaying = true;
          playbackStartTime = millis();
          packetCount = 0;
          return;
        }
      }
      
      // Check if this is the start of audio playback
      if (!isPlaying) {
        isPlaying = true;
        playbackStartTime = millis();
        packetCount = 0;
        Serial.println("=== Audio Playback Started ===");
      }
      
      packetCount++;
      
      // Print progress every 100 packets
      if (packetCount % 100 == 0) {
        Serial.printf("Received %lu packets\n", packetCount);
      }
      
      // Convert stereo to mono (WAV is stereo, but we output mono)
      int monoBytes = convertStereoToMono(audioBuffer, len, monoBuffer, BUFFER_SIZE / 2);
      
      // Play the audio data immediately
      size_t written = 0;
      esp_err_t err = i2s_write(I2S_NUM_0, monoBuffer, monoBytes, &written, 100 / portTICK_RATE_MS);
      
      if (err != ESP_OK) {
        Serial.printf("I2S write error: %d\n", err);
      }
    }
  }
  
  // Check if playback has timed out (no packets for 500ms = end of stream)
  if (isPlaying && (millis() - lastPacketTime > 500)) {
    isPlaying = false;
    Serial.println("=== Audio Playback Complete ===");
    Serial.printf("Total packets: %lu, duration: %lu ms\n", packetCount, millis() - playbackStartTime);
    
    // Clear I2S buffer to prevent clicking
    int16_t silence[64] = {0};
    for (int i = 0; i < 16; i++) {
      size_t written;
      i2s_write(I2S_NUM_0, silence, sizeof(silence), &written, 10 / portTICK_RATE_MS);
    }
    
    // Play completion beep
    playBeep(1500, 100);
    delay(50);
    playBeep(2000, 100);
    
    Serial.println("Ready for next audio...\n");
  }
  
  // Small delay to prevent watchdog issues
  delay(1);
}
