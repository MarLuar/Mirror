/**
 * @file audio_processing_helper.h
 * @brief Helper functions for audio processing
 */

#ifndef AUDIO_PROCESSING_HELPER_H
#define AUDIO_PROCESSING_HELPER_H

#include "Arduino.h"
#include <math.h>

// Function to normalize audio data
void normalizeAudio(int16_t* data, size_t length) {
  // Find the maximum amplitude
  int16_t maxAmplitude = 0;
  for (size_t i = 0; i < length; i++) {
    int16_t absVal = abs(data[i]);
    if (absVal > maxAmplitude) {
      maxAmplitude = absVal;
    }
  }

  // Normalize if the signal is too quiet
  if (maxAmplitude > 0 && maxAmplitude < 32767) {
    float gain = 32767.0f / maxAmplitude;
    for (size_t i = 0; i < length; i++) {
      // Apply gain but clamp to prevent overflow
      float val = data[i] * gain;
      if (val > 32767) val = 32767;
      else if (val < -32768) val = -32768;
      data[i] = (int16_t)val;
    }
  }
}

// Function to detect if there's significant audio activity
bool hasSignificantAudio(int16_t* data, size_t length, int threshold = 1000) {
  for (size_t i = 0; i < length; i++) {
    if (abs(data[i]) > threshold) {
      return true;
    }
  }
  return false;
}

// Function to calculate RMS (Root Mean Square) of audio data
float calculateRMS(int16_t* data, size_t length) {
  if (length == 0) return 0.0f;

  double sum = 0.0;
  for (size_t i = 0; i < length; i++) {
    sum += (double)data[i] * data[i];
  }
  return sqrt(sum / (double)length);
}

#endif // AUDIO_PROCESSING_HELPER_H