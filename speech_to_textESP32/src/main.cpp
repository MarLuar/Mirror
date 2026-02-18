#include "driver/i2s.h"
#include "esp_http_client.h"
#include "esp_https_ota.h"
#include "esp_log.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "nvs_flash.h"
#include "sdkconfig.h"
#include <WiFi.h>
#include <SD.h>
#include <SPI.h>

// Include the audio processing helper
#include "audio_processing_helper.h"

// Pin definitions
#define I2S_WS      25
#define I2S_SCK     27
#define I2S_SD      14  // Assuming this is the SD pin for the microphone
#define BUTTON_PIN  14

// SD Card pins
#define SD_MISO     19
#define SD_MOSI     23
#define SD_SCK      18
#define SD_CS       5

// WiFi credentials
const char* ssid = "Iphone SE";
const char* password = "koogsthegroopa";

// Audio configuration
const i2s_port_t I2S_PORT = I2S_NUM_0;
const int SAMPLE_RATE = 16000;
const int SAMPLE_BITS = 16;
const int CHANNEL_NUMBER = 1;

// Buffer configuration
const int RECORD_TIME = 2; // Reduce record time to 2 seconds to save memory
const int BUFFER_SIZE = SAMPLE_RATE * RECORD_TIME * SAMPLE_BITS / 8; // ~64KB instead of ~160KB
uint8_t* buffer = NULL;

bool recording = false;
bool button_pressed = false;

void setup() {
  Serial.begin(115200);

  // Initialize SD card
  if (!SD.begin(SD_CS)) {
    Serial.println("Card Mount Failed");
    return;
  }
  uint8_t cardType = SD.cardType();
  if (cardType == CARD_NONE) {
    Serial.println("No SD card attached");
    return;
  }
  Serial.println("SD Card initialized.");

  // Initialize button
  pinMode(BUTTON_PIN, INPUT_PULLUP);

  // Connect to WiFi
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.print(".");
  }
  Serial.println();
  Serial.println("WiFi connected!");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());

  // Initialize I2S
  configureI2S();

  // Allocate buffer for audio data
  buffer = (uint8_t*)malloc(BUFFER_SIZE);
  if (buffer == NULL) {
    Serial.println("Buffer allocation failed!");
    return;
  }

  Serial.println("Setup complete. Press button to record audio.");
}

void loop() {
  // Check button state
  bool current_button_state = !digitalRead(BUTTON_PIN); // Active low

  if (current_button_state && !button_pressed) {
    button_pressed = true;
    Serial.println("Button pressed - Starting recording...");
    startRecording();
  } else if (!current_button_state) {
    button_pressed = false;
  }

  delay(50);
}

void configureI2S() {
  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = i2s_bits_per_sample_t(SAMPLE_BITS),
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 4,
    .dma_buf_len = 1024,
    .use_apll = false,
    .tx_desc_auto_clear = false,
    .fixed_mclk = 0
  };

  i2s_pin_config_t pin_config = {
    .bck_io_num = I2S_SCK,
    .ws_io_num = I2S_WS,
    .data_out_num = -1,
    .data_in_num = I2S_SD
  };

  i2s_driver_install(I2S_PORT, &i2s_config, 0, NULL);
  i2s_set_pin(I2S_PORT, &pin_config);
  i2s_zero_dma_buffer(I2S_PORT);
}

void startRecording() {
  recording = true;

  size_t bytes_read = 0;
  int total_bytes = 0;

  Serial.println("Recording started...");

  // Clear the buffer
  memset(buffer, 0, BUFFER_SIZE);

  // Calculate chunk size for each second of recording
  int chunk_size = SAMPLE_RATE * SAMPLE_BITS / 8; // bytes per second

  // Record for RECORD_TIME seconds
  for (int i = 0; i < RECORD_TIME; i++) {
    if ((total_bytes + chunk_size) > BUFFER_SIZE) {
      // Prevent buffer overflow
      chunk_size = BUFFER_SIZE - total_bytes;
      if (chunk_size <= 0) break;
    }

    i2s_read(I2S_PORT, &buffer[total_bytes], chunk_size, &bytes_read, portMAX_DELAY);
    total_bytes += bytes_read;

    Serial.printf("Recorded %d bytes (%d seconds)\n", bytes_read, i+1);
  }

  Serial.printf("Recording finished. Total bytes recorded: %d\n", total_bytes);

  if (total_bytes > 0) {
    // Convert to int16_t for processing
    int16_t* samples = (int16_t*)buffer;
    int sample_count = total_bytes / sizeof(int16_t);

    // Process the audio data
    normalizeAudio(samples, sample_count);
    float rms = calculateRMS(samples, sample_count);

    Serial.printf("Audio RMS: %.2f\n", rms);

    // Check if there's significant audio activity
    if (hasSignificantAudio(samples, sample_count)) {
      Serial.println("Significant audio detected!");

      // Save audio data to SD card
      String filename = "/audio_" + String(millis()) + ".raw";
      File audioFile = SD.open(filename.c_str(), FILE_WRITE);
      if (audioFile) {
        audioFile.write(buffer, total_bytes);
        audioFile.close();
        Serial.println("Audio saved to SD card: " + filename);

        // Process audio (placeholder for actual speech-to-text)
        processAudio(total_bytes);
      } else {
        Serial.println("Failed to save audio to SD card");
      }
    } else {
      Serial.println("No significant audio detected, not saving file.");
    }
  } else {
    Serial.println("No audio data recorded.");
  }

  recording = false;
}

void processAudio(int bytes_recorded) {
  Serial.println("Processing audio data...");

  // In a real implementation, you would send the audio data to a speech-to-text service
  // For now, we'll just simulate processing

  // Example: Print some statistics about the recorded data
  int16_t* samples = (int16_t*)buffer;
  int sample_count = bytes_recorded / sizeof(int16_t);

  int max_amplitude = 0;
  for (int i = 0; i < sample_count; i++) {
    int amplitude = abs(samples[i]);
    if (amplitude > max_amplitude) {
      max_amplitude = amplitude;
    }
  }

  Serial.printf("Audio stats - Samples: %d, Max amplitude: %d\n", sample_count, max_amplitude);

  // Placeholder for actual speech recognition
  Serial.println("Speech recognition would happen here...");
  Serial.println("In a real implementation, you would send the audio data to a service like Google Speech-to-Text API");
}