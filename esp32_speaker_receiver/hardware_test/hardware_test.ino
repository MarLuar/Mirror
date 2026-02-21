/*
 * ESP32 Speaker Hardware Test
 * Generates test tones internally to verify amplifier and speaker work
 * 
 * If this doesn't produce sound, check your wiring!
 */

#include <driver/i2s.h>

// I2S Pin Definitions (MAX98357A Amplifier)
#define AMP_BCLK    27
#define AMP_LRCK    26
#define AMP_DIN     14

// Audio settings
#define SAMPLE_RATE 44100

void initI2S() {
  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,  // Mono
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
  Serial.println("I2S initialized");
}

void playTone(int frequency, int duration_ms, float volume = 0.5) {
  int samples = (SAMPLE_RATE * duration_ms) / 1000;
  int16_t buffer[64];
  
  Serial.printf("Playing %d Hz for %d ms (volume: %.0f%%)\n", frequency, duration_ms, volume * 100);
  
  int maxAmplitude = (int)(32767 * volume);  // Scale by volume
  
  for (int i = 0; i < samples; i += 64) {
    int chunk = min(64, samples - i);
    for (int j = 0; j < chunk; j++) {
      float t = (float)(i + j) / SAMPLE_RATE;
      buffer[j] = (int16_t)(maxAmplitude * sin(2 * PI * frequency * t));
    }
    size_t written;
    i2s_write(I2S_NUM_0, buffer, chunk * sizeof(int16_t), &written, portMAX_DELAY);
  }
  
  // Clear buffer
  int16_t silence[64] = {0};
  for (int i = 0; i < 4; i++) {
    size_t written;
    i2s_write(I2S_NUM_0, silence, sizeof(silence), &written, portMAX_DELAY);
  }
}

void playSiren() {
  Serial.println("Playing siren sound...");
  for (int i = 0; i < 5; i++) {
    // Rising tone
    for (int freq = 400; freq <= 1200; freq += 50) {
      playTone(freq, 20, 0.7);
    }
    // Falling tone
    for (int freq = 1200; freq >= 400; freq -= 50) {
      playTone(freq, 20, 0.7);
    }
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n===================================");
  Serial.println("ESP32 Speaker Hardware Test");
  Serial.println("===================================");
  Serial.println("\nWiring Check:");
  Serial.println("  MAX98357A VCC -> 5V (or 3.3V)");
  Serial.println("  MAX98357A GND -> GND");
  Serial.println("  MAX98357A BCLK -> GPIO 26");
  Serial.println("  MAX98357A LRC -> GPIO 27");
  Serial.println("  MAX98357A DIN -> GPIO 14");
  Serial.println("  MAX98357A SD -> 5V (or 3.3V) [MUST BE HIGH!]");
  Serial.println("  Speaker -> SPK+ and SPK-");
  Serial.println("===================================\n");
  
  initI2S();
  
  Serial.println("Starting audio test in 3 seconds...");
  delay(3000);
}

void loop() {
  Serial.println("\n--- Test Sequence ---");
  
  // Test 1: Low frequency
  Serial.println("\n[1/5] Low frequency test (400 Hz)");
  playTone(400, 1000, 0.8);
  delay(500);
  
  // Test 2: Mid frequency
  Serial.println("[2/5] Mid frequency test (1000 Hz)");
  playTone(1000, 1000, 0.8);
  delay(500);
  
  // Test 3: High frequency
  Serial.println("[3/5] High frequency test (2000 Hz)");
  playTone(2000, 1000, 0.8);
  delay(500);
  
  // Test 4: Volume sweep
  Serial.println("[4/5] Volume sweep (1000 Hz, increasing volume)");
  for (float vol = 0.1; vol <= 1.0; vol += 0.1) {
    Serial.printf("  Volume: %.0f%%\n", vol * 100);
    playTone(1000, 200, vol);
    delay(100);
  }
  
  // Test 5: Siren
  Serial.println("[5/5] Siren sound");
  playSiren();
  
  Serial.println("\n✅ Test sequence complete!");
  Serial.println("If you heard sounds, your hardware is working!");
  Serial.println("If silent, check wiring and SD pin connection.");
  Serial.println("\nWaiting 10 seconds before repeating...");
  Serial.println("Send any character to restart immediately.");
  
  // Wait with serial check
  for (int i = 0; i < 100; i++) {
    delay(100);
    if (Serial.available()) {
      Serial.read();
      Serial.println("Restarting...");
      break;
    }
  }
}
