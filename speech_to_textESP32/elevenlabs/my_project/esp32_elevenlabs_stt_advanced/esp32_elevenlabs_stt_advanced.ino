/*
 * ESP32 Audio Recorder with ElevenLabs Speech-to-Text
 * Advanced memory-optimized version with streaming upload
 * Modified for custom hardware setup with SD card module and external I2S microphone
 */

#include "driver/i2s.h"
#include "driver/gpio.h"
#include <Arduino.h>
#include "FS.h"
#include "SD.h"
#include "SPI.h"
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include "esp_heap_caps.h"
#include <WiFiClientSecure.h>

long now, total_time;
// WiFi credentials
const char* ssid = "Iphone SE";         // Replace with your WiFi SSID
const char* password = "koogsthegroopa"; // Replace with your WiFi password

// ElevenLabs API configuration
const char* elevenlabs_api_key = "sk_32ecab6e7915fe60d18bf5e3599c57bb7163d06b0c5e379b"; // Replace with your ElevenLabs API key
const char* elevenlabs_stt_url = "https://api.elevenlabs.io/v1/speech-to-text";

// Audio recording settings
#define WAV_FILE_NAME "recording"
#define SAMPLE_RATE 16000U
#define SAMPLE_BITS 16
#define WAV_HEADER_SIZE 44
#define VOLUME_GAIN 2

// I2S Configuration for external I2S microphone
#define I2S_WS      25          // Word Select (LRC)
#define I2S_SCK     27          // Serial Clock (BCLK)
#define I2S_SD      26          // Serial Data (DATA)

// SD Card Module pins
#define SD_MISO     19
#define SD_MOSI     23
#define SD_SCK      18
#define SD_CS       5           // Chip Select

// Button pin
#define BUTTON_PIN  14

bool isPressed = false;

// Global variables
bool recording_active = false;
String last_transcription = "";
bool wifi_connected = false;
String current_recording_file = "";

// ===== FUNCTION DECLARATIONS =====
bool connectToWiFi();
bool init_i2s();
void deinit_i2s();
void cleanupOldRecordings();
void record_wav_streaming();
void process_recording();
String send_to_elevenlabs_stt_streaming(String filename);
void generate_wav_header(uint8_t* wav_header, uint32_t wav_size, uint32_t sample_rate);

// ===== IMPLEMENTATION =====

bool init_i2s() {
  Serial.println("Initializing I2S for external microphone...");

  // Configure I2S
  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_RIGHT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 4,
    .dma_buf_len = 1024,
    .use_apll = false,
    .tx_desc_auto_clear = false,
    .fixed_mclk = 0
  };

  // Install and configure I2S driver
  esp_err_t err = i2s_driver_install(I2S_NUM_0, &i2s_config, 0, NULL);
  if (err != ESP_OK) {
    Serial.printf("Failed to install I2S driver: %s\n", esp_err_to_name(err));
    return false;
  }

  // Configure pins
  i2s_pin_config_t pin_config = {
    .bck_io_num = I2S_SCK,
    .ws_io_num = I2S_WS,
    .data_out_num = -1, // Not used
    .data_in_num = I2S_SD
  };

  err = i2s_set_pin(I2S_NUM_0, &pin_config);
  if (err != ESP_OK) {
    Serial.printf("Failed to set I2S pin config: %s\n", esp_err_to_name(err));
    i2s_driver_uninstall(I2S_NUM_0);
    return false;
  }

  Serial.println("I2S initialized successfully");
  return true;
}

void deinit_i2s() {
  i2s_driver_uninstall(I2S_NUM_0);
}

bool connectToWiFi() {
  Serial.println("Connecting to WiFi...");
  WiFi.disconnect();
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 40) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi connected!");
    Serial.print("IP: ");
    Serial.println(WiFi.localIP());
    wifi_connected = true;
    return true;
  } else {
    Serial.println("\nWiFi connection failed");
    wifi_connected = false;
    return false;
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(BUTTON_PIN, INPUT_PULLUP);

  // Small delay to ensure stable power
  delay(1000);

  // Initialize I2S for external microphone
  if (!init_i2s()) {
    Serial.println("I2S init failed!");
    while (1)
      ;
  }

  // Initialize SD card with custom pins
  SPI.begin(SD_SCK, SD_MISO, SD_MOSI, SD_CS);
  if (!SD.begin(SD_CS)) {
    Serial.println("Failed to mount SD Card!");
    while (1)
      ;
  }
  Serial.println("SD Card initialized with custom pins");

  cleanupOldRecordings();
  connectToWiFi();
}

void loop() {
  bool currentState = digitalRead(BUTTON_PIN) == LOW;

  if (currentState && !isPressed) {
    isPressed = true;
    Serial.println("Button pressed → start recording");
    record_wav_streaming();
    process_recording();
  }

  if (!currentState && isPressed) {
    isPressed = false;
    Serial.println("Button released");
  }

  delay(50);
}

void record_wav_streaming() {
  const uint32_t max_record_time = 15;  // Increased back to 15 seconds with streaming approach

  String filename = "/" + String(WAV_FILE_NAME) + "_" + String(millis()) + ".wav";
  current_recording_file = filename;

  File file = SD.open(filename.c_str(), FILE_WRITE);
  if (!file) {
    Serial.println("Failed to open file");
    current_recording_file = "";
    return;
  }

  uint8_t wav_header[WAV_HEADER_SIZE];
  generate_wav_header(wav_header, 0, SAMPLE_RATE);
  file.write(wav_header, WAV_HEADER_SIZE);

  uint8_t* buffer = (uint8_t*)malloc(1024);
  if (!buffer) {
    Serial.println("Failed to allocate buffer");
    file.close();
    current_recording_file = "";
    return;
  }

  recording_active = true;
  size_t total_bytes = 0;
  unsigned long startTime = millis();

  Serial.println("Recording...");

  while (digitalRead(BUTTON_PIN) == LOW && (millis() - startTime < max_record_time * 1000)) {
    size_t bytes_read = 0;
    esp_err_t ret = i2s_read(I2S_NUM_0, buffer, 1024, &bytes_read, pdMS_TO_TICKS(100));
    
    if (ret != ESP_OK) {
      Serial.printf("I2S read failed: %s\n", esp_err_to_name(ret));
      continue;
    }

    // Process audio samples to adjust volume
    for (size_t i = 0; i < bytes_read; i += 2) {
      int16_t* sample = (int16_t*)&buffer[i];
      int32_t amp = (*sample) << VOLUME_GAIN;
      if (amp > 32767) amp = 32767;
      if (amp < -32768) amp = -32768;
      *sample = (int16_t)amp;
    }

    file.write(buffer, bytes_read);
    total_bytes += bytes_read;
  }

  recording_active = false;
  free(buffer);

  // Update WAV header with correct file size
  file.seek(0);
  generate_wav_header(wav_header, total_bytes, SAMPLE_RATE);
  file.write(wav_header, WAV_HEADER_SIZE);
  file.close();

  Serial.printf("Recording finished: %s (%d bytes)\n", filename.c_str(), total_bytes);
}

void process_recording() {
  if (current_recording_file.isEmpty()) return;

  Serial.printf("Sending %s to ElevenLabs...\n", current_recording_file.c_str());
  String transcription = send_to_elevenlabs_stt_streaming(current_recording_file);

  if (transcription.length()) {
    Serial.println("Transcription:");
    Serial.println(transcription);
    last_transcription = transcription;
  } else {
    Serial.println("STT failed");
  }

  current_recording_file = "";
}

String send_to_elevenlabs_stt_streaming(String filename) {
  uint32_t t_start = millis();

  if (!wifi_connected || WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi not connected, cannot send to STT");
    return "";
  }

  File file = SD.open(filename.c_str());
  if (!file) {
    Serial.println("Failed to open audio file");
    return "";
  }

  size_t file_size = file.size();
  if (file_size > 500000) { // Allow up to 500KB with streaming approach
    Serial.println("File too large for STT request (>500KB)");
    file.close();
    return "";
  }

  // Check if file has content
  if (file_size <= WAV_HEADER_SIZE) {
    Serial.println("File is too small (probably empty)");
    file.close();
    return "";
  }

  uint32_t t_file_loaded = millis();

  // Create HTTPS client for ElevenLabs API
  WiFiClientSecure client;
  client.setInsecure(); // Skip certificate validation for speed

  if (!client.connect("api.elevenlabs.io", 443)) {
    Serial.println("Connection to ElevenLabs API failed");
    file.close();
    return "";
  }

  // Prepare multipart form data
  String boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW";

  // Build the HTTP request
  String httpRequest = "POST /v1/speech-to-text HTTP/1.1\r\n";
  httpRequest += "Host: api.elevenlabs.io\r\n";
  httpRequest += "xi-api-key: " + String(elevenlabs_api_key) + "\r\n";
  httpRequest += "Content-Type: multipart/form-data; boundary=" + boundary + "\r\n";

  // Calculate total content length
  String body_start = "--" + boundary + "\r\n";
  body_start += "Content-Disposition: form-data; name=\"model_id\"\r\n\r\n";
  body_start += "scribe_v1\r\n";
  body_start += "--" + boundary + "\r\n";
  body_start += "Content-Disposition: form-data; name=\"file\"; filename=\"audio.wav\"\r\n";
  body_start += "Content-Type: audio/wav\r\n\r\n";

  String body_end = "\r\n--" + boundary + "--\r\n";
  size_t total_length = body_start.length() + file_size + body_end.length();
  
  httpRequest += "Content-Length: " + String(total_length) + "\r\n";
  httpRequest += "Connection: close\r\n\r\n";

  // Send the HTTP request header
  client.print(httpRequest);

  // Send the multipart header
  client.print(body_start);

  // Stream the file content in chunks
  uint8_t* chunk_buffer = (uint8_t*)malloc(1024);
  if (chunk_buffer) {
    size_t bytes_sent = 0;
    file.seek(0); // Make sure we're at the beginning of the file
    
    while (bytes_sent < file_size) {
      size_t chunk_size = min((size_t)1024, file_size - bytes_sent);
      size_t bytes_read = file.read(chunk_buffer, chunk_size);
      
      if (bytes_read == 0) break; // End of file
      
      client.write(chunk_buffer, bytes_read);
      bytes_sent += bytes_read;
    }
    free(chunk_buffer);
  }

  // Send the multipart footer
  client.print(body_end);

  file.close();

  // Wait for response
  unsigned long timeout = millis();
  while (client.available() == 0) {
    if (millis() - timeout > 15000) { // 15 second timeout
      Serial.println(">>> Client Response Timeout !");
      client.stop();
      return "";
    }
    delay(10);
  }

  // Read the response
  String response = client.readString();
  client.stop();

  uint32_t t_response_received = millis();

  String transcription = "";
  // Look for HTTP 200 in the response
  if (response.indexOf("200 OK") != -1) {
    Serial.printf("HTTP 200 OK\nPartial Response: %.100s...\n", response.c_str());
    DynamicJsonDocument doc(2048);
    DeserializationError error = deserializeJson(doc, response.substring(response.indexOf('{')));
    if (error == DeserializationError::Ok) {
      if (doc.containsKey("text") && !doc["text"].as<String>().isEmpty()) {
        transcription = doc["text"].as<String>();
      } else {
        Serial.println("API returned empty transcription - possibly low audio quality or silence");
      }
    } else {
      Serial.println("Failed to parse JSON response");
      Serial.println("Parse error: " + String(error.c_str()));
    }
  } else {
    Serial.printf("HTTP Error in response\nResponse: %.200s\n", response.c_str());
  }

  uint32_t t_response_parsed = millis();

  // Print detailed timing information
  Serial.println("---------------------------------------------------");
  Serial.printf("-> Audio File [%s] size: %d bytes\n", filename.c_str(), file_size);
  Serial.printf("-> Latency File Loading [t_file_loaded]:     %.3f sec\n", (float)(t_file_loaded - t_start) / 1000);
  Serial.printf("-> Latency ElevenLabs STT Response:          %.3f sec\n", (float)(t_response_received - t_start) / 1000);
  Serial.printf("-> Latency Response Parsing:                 %.3f sec\n", (float)(t_response_parsed - t_response_received) / 1000);
  Serial.printf("=> TOTAL Duration [sec]: .................... %.3f sec\n", (float)(t_response_parsed - t_start) / 1000);
  Serial.printf("=> Server response length [bytes]: %d\n", response.length());
  Serial.printf("=> Transcription: [%s]\n", transcription.c_str());
  Serial.println("---------------------------------------------------");

  return transcription;
}

void generate_wav_header(uint8_t* wav_header, uint32_t wav_size, uint32_t sample_rate) {
  uint32_t file_size = wav_size + WAV_HEADER_SIZE - 8;
  uint32_t byte_rate = sample_rate * SAMPLE_BITS / 8;

  const uint8_t header[] = {
    'R',
    'I',
    'F',
    'F',
    (uint8_t)(file_size & 0xFF),
    (uint8_t)((file_size >> 8) & 0xFF),
    (uint8_t)((file_size >> 16) & 0xFF),
    (uint8_t)((file_size >> 24) & 0xFF),
    'W',
    'A',
    'V',
    'E',
    'f',
    'm',
    't',
    ' ',
    0x10,
    0x00,
    0x00,
    0x00,
    0x01,
    0x00,
    0x01,
    0x00,
    (uint8_t)(sample_rate & 0xFF),
    (uint8_t)((sample_rate >> 8) & 0xFF),
    (uint8_t)((sample_rate >> 16) & 0xFF),
    (uint8_t)((sample_rate >> 24) & 0xFF),
    (uint8_t)(byte_rate & 0xFF),
    (uint8_t)((byte_rate >> 8) & 0xFF),
    (uint8_t)((byte_rate >> 16) & 0xFF),
    (uint8_t)((byte_rate >> 24) & 0xFF),
    0x02,
    0x00,
    0x10,
    0x00,
    'd',
    'a',
    't',
    'a',
    (uint8_t)(wav_size & 0xFF),
    (uint8_t)((wav_size >> 8) & 0xFF),
    (uint8_t)((wav_size >> 16) & 0xFF),
    (uint8_t)((wav_size >> 24) & 0xFF),
  };
  memcpy(wav_header, header, sizeof(header));
}

void cleanupOldRecordings() {
  File root = SD.open("/");
  if (!root) {
    Serial.println("Failed to open root directory");
    return;
  }
  
  File file = root.openNextFile();
  while (file) {
    String filename = file.name();
    if (filename.startsWith(WAV_FILE_NAME) && filename.endsWith(".wav")) {
      Serial.printf("Removing old recording: %s\n", filename.c_str());
      file.close();
      SD.remove(filename.c_str());
    } else {
      file.close();
    }
    file = root.openNextFile();
  }
  root.close();
}