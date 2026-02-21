// Simple ESP32 Beep Test - MAX98357A
// Generates a continuous beep to test speaker wiring

#include <driver/i2s.h>

// MAX98357A Pins
#define BCLK  27
#define LRC   26
#define DIN   14

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("Simple Beep Test");
  Serial.println("VCC->5V, GND->GND, BCLK->26, LRC->27, DIN->14, SD->5V");
  
  // I2S Config
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
    .bck_io_num = BCLK,
    .ws_io_num = LRC,
    .data_out_num = DIN,
    .data_in_num = I2S_PIN_NO_CHANGE
  };
  
  i2s_set_pin(I2S_NUM_0, &pins);
  
  Serial.println("Playing 1kHz beep...");
}

void loop() {
  // Generate 1000 Hz sine wave
  int16_t sample;
  static int phase = 0;
  
  for (int i = 0; i < 64; i++) {
    // 1000 Hz at 44100 sample rate
    sample = (int16_t)(20000 * sin(phase * 2 * PI / 44));
    phase++;
    if (phase >= 44) phase = 0;
    
    size_t written;
    i2s_write(I2S_NUM_0, &sample, 2, &written, portMAX_DELAY);
  }
}
