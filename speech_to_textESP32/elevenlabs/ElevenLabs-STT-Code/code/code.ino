
/*
 * XIAO ESP32S3 Audio Recorder with ElevenLabs Speech-to-Text
 * Clean STT-only version (no ESP-NOW)
 */

#include "driver/i2s_pdm.h"
#include "driver/gpio.h"
#include <Arduino.h>
#include "FS.h"
#include "SD.h"
#include "SPI.h"
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

long now, total_time;
// WiFi credentials
const char* ssid = "SSID";
const char* password = "PASS";

// ElevenLabs API configuration
const char* elevenlabs_api_key = "API KEY";
const char* elevenlabs_stt_url = "https://api.elevenlabs.io/v1/speech-to-text";

// Audio recording settings
#define WAV_FILE_NAME "recording"
#define SAMPLE_RATE 16000U
#define SAMPLE_BITS 16
#define WAV_HEADER_SIZE 44
#define VOLUME_GAIN 2

// I2S PDM Configuration for XIAO ESP32S3 built-in microphone
#define I2S_NUM I2S_NUM_0
#define PDM_CLK_GPIO (gpio_num_t)42
#define PDM_DIN_GPIO (gpio_num_t)41

#define BUTTON_PIN D1
bool isPressed = false;

// I2S handle
i2s_chan_handle_t rx_handle = NULL;

// Global variables
bool recording_active = false;
String last_transcription = "";
bool wifi_connected = false;
String current_recording_file = "";

// ===== FUNCTION DECLARATIONS =====
bool connectToWiFi();
bool init_i2s_pdm();
void deinit_i2s_pdm();
void cleanupOldRecordings();
void record_wav_streaming();
void process_recording();
String send_to_elevenlabs_stt(String filename);
void generate_wav_header(uint8_t* wav_header, uint32_t wav_size, uint32_t sample_rate);

// ===== IMPLEMENTATION =====

bool init_i2s_pdm() {
  Serial.println("Initializing I2S PDM...");

  i2s_chan_config_t chan_cfg = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM, I2S_ROLE_MASTER);
  chan_cfg.auto_clear = true;

  if (i2s_new_channel(&chan_cfg, NULL, &rx_handle) != ESP_OK) {
    Serial.println("Failed to create I2S channel");
    return false;
  }

  i2s_pdm_rx_config_t pdm_rx_cfg = {
    .clk_cfg = I2S_PDM_RX_CLK_DEFAULT_CONFIG(SAMPLE_RATE),
    .slot_cfg = I2S_PDM_RX_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO),
    .gpio_cfg = {
      .clk = PDM_CLK_GPIO,
      .din = PDM_DIN_GPIO,
      .invert_flags = { .clk_inv = false },
    },
  };

  if (i2s_channel_init_pdm_rx_mode(rx_handle, &pdm_rx_cfg) != ESP_OK) return false;
  if (i2s_channel_enable(rx_handle) != ESP_OK) return false;

  Serial.println("I2S PDM initialized successfully");
  return true;
}

void deinit_i2s_pdm() {
  if (rx_handle != NULL) {
    i2s_channel_disable(rx_handle);
    i2s_del_channel(rx_handle);
    rx_handle = NULL;
  }
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

  if (!init_i2s_pdm()) {
    Serial.println("I2S init failed!");
    while (1)
      ;
  }

  if (!SD.begin(21)) {
    Serial.println("Failed to mount SD Card!");
    while (1)
      ;
  }
  Serial.println("SD Card initialized");

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
// remove: long now, total_time;



void record_wav_streaming() {
  if (rx_handle == NULL) return;

  const uint32_t max_record_time = 30;  // sec

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

  uint8_t* buffer = (uint8_t*)malloc(512);
  if (!buffer) return;

  recording_active = true;
  size_t total_bytes = 0;
  unsigned long startTime = millis();

  Serial.println("Recording...");

  while (digitalRead(BUTTON_PIN) == LOW && (millis() - startTime < max_record_time * 1000)) {
    size_t bytes_read = 0;
    if (i2s_channel_read(rx_handle, buffer, 512, &bytes_read, pdMS_TO_TICKS(100)) != ESP_OK) continue;

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

  file.seek(0);
  generate_wav_header(wav_header, total_bytes, SAMPLE_RATE);
  file.write(wav_header, WAV_HEADER_SIZE);
  file.close();

  Serial.printf("Recording finished: %s (%d bytes)\n", filename.c_str(), total_bytes);
}

void process_recording() {
  if (current_recording_file.isEmpty()) return;

  Serial.printf("Sending %s to ElevenLabs...\n", current_recording_file.c_str());
  String transcription = send_to_elevenlabs_stt(current_recording_file);

  if (transcription.length()) {
    Serial.println("Transcription:");
    Serial.println(transcription);
    last_transcription = transcription;
  } else {
    Serial.println("STT failed");
  }

  current_recording_file = "";
}
String send_to_elevenlabs_stt(String filename) {
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
  if (file_size > 500000) {
    Serial.println("File too large for STT request (>500KB)");
    file.close();
    return "";
  }

  uint8_t* audio_data = (uint8_t*)malloc(file_size);
  if (!audio_data) {
    Serial.println("Failed to allocate memory for audio data!");
    file.close();
    return "";
  }
  size_t bytesRead = file.read(audio_data, file_size);
  file.close();

  uint32_t t_file_loaded = millis();

  HTTPClient http;
  if (!http.begin(elevenlabs_stt_url)) {
    Serial.println("Failed to initialize HTTP connection");
    free(audio_data);
    return "";
  }

  http.setTimeout(30000);
  http.setConnectTimeout(10000);
  http.addHeader("xi-api-key", elevenlabs_api_key);

  String boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW";
  http.addHeader("Content-Type", "multipart/form-data; boundary=" + boundary);

  String body_start = "--" + boundary + "\r\n";
  body_start += "Content-Disposition: form-data; name=\"model_id\"\r\n\r\n";
  body_start += "scribe_v1\r\n";
  body_start += "--" + boundary + "\r\n";
  body_start += "Content-Disposition: form-data; name=\"file\"; filename=\"audio.wav\"\r\n";
  body_start += "Content-Type: audio/wav\r\n\r\n";

  String body_end = "\r\n--" + boundary + "--\r\n";
  size_t total_size = body_start.length() + file_size + body_end.length();
  uint8_t* complete_body = (uint8_t*)malloc(total_size);

  memcpy(complete_body, body_start.c_str(), body_start.length());
  memcpy(complete_body + body_start.length(), audio_data, file_size);
  memcpy(complete_body + body_start.length() + file_size, body_end.c_str(), body_end.length());

  free(audio_data);

  uint32_t t_request_prepared = millis();

  Serial.println("Sending request to ElevenLabs STT...");

  // Start timer just before POST
  uint32_t t_request_sent = millis();
  int httpResponseCode = http.POST(complete_body, total_size);
  // Stop timer after response received
  uint32_t t_response_received = millis();

  free(complete_body);

  String transcription = "";
  String response = http.getString();

  uint32_t t_response_parsed = millis();

  if (httpResponseCode == 200) {
    Serial.printf("HTTP 200 OK\nResponse: %s\n", response.c_str());
    DynamicJsonDocument doc(2048);
    if (deserializeJson(doc, response) == DeserializationError::Ok) {
      if (doc.containsKey("text")) {
        transcription = doc["text"].as<String>();
      }
    }
  } else {
    Serial.printf("HTTP Error: %d\n", httpResponseCode);
    Serial.println("Response: " + response);
  }

  http.end();

  // Print detailed timing information (similar to Deepgram implementation)
  Serial.println("---------------------------------------------------");
  Serial.printf("-> Audio File [%s] size: %d bytes\n", filename.c_str(), file_size);
  Serial.printf("-> Latency File Loading [t_file_loaded]:     %.3f sec\n", (float)(t_file_loaded - t_start) / 1000);
  Serial.printf("-> Latency Request Preparation:              %.3f sec\n", (float)(t_request_prepared - t_file_loaded) / 1000);
  Serial.printf("-> Latency ElevenLabs STT Response:          %.3f sec\n", (float)(t_response_received - t_request_sent) / 1000);
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
    file_size,
    file_size >> 8,
    file_size >> 16,
    file_size >> 24,
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
    sample_rate,
    sample_rate >> 8,
    sample_rate >> 16,
    sample_rate >> 24,
    byte_rate,
    byte_rate >> 8,
    byte_rate >> 16,
    byte_rate >> 24,
    0x02,
    0x00,
    0x10,
    0x00,
    'd',
    'a',
    't',
    'a',
    wav_size,
    wav_size >> 8,
    wav_size >> 16,
    wav_size >> 24,
  };
  memcpy(wav_header, header, sizeof(header));
}

void cleanupOldRecordings() {
  File root = SD.open("/");
  File file = root.openNextFile();
  while (file) {
    String filename = file.name();
    if (filename.startsWith(WAV_FILE_NAME) && filename.endsWith(".wav")) {
      file.close();
      SD.remove("/" + filename);
    } else {
      file.close();
    }
    file = root.openNextFile();
  }
  root.close();
}
