/*
 * ESP32-CAM (AI Thinker) MJPEG Stream Server
 * 
 * Features:
 * - MJPEG HTTP streaming for ffmpeg capture
 * - ESP-NOW trigger support (from another ESP device)
 * - Serial command trigger support
 * - Static IP configuration
 * 
 * Network Settings:
 * - SSID: ubuntu
 * - DHCP: Enabled (Auto IP Assignment)
 * - Check Serial Monitor for assigned IP
 */

#include <WiFi.h>
#include <esp_now.h>
#include "esp_camera.h"
#include "esp_timer.h"
#include "img_converters.h"
#include "Arduino.h"
#include "fb_gfx.h"
#include "soc/soc.h"
#include "soc/rtc_cntl_reg.h"
#include "esp_http_server.h"
#include <FS.h>
#include <SD_MMC.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// ===================
// WiFi Configuration
// ===================
const char* ssid = "ubuntu";
const char* password = "ubuntubuntu";

// DHCP Configuration (Auto IP Assignment)
// The ESP32 will automatically get an IP from the hotspot
// Check Serial Monitor to see the assigned IP

// ===================
// ESP-NOW Configuration
// ===================
typedef struct struct_message {
  char command[32];
  bool record;
} struct_message;

struct_message incomingData;
volatile bool recordingRequested = false;
volatile bool isRecording = false;
unsigned long recordingStartTime = 0;

// SD Card Recording
bool sdCardAvailable = false;
File mjpegFile;
char currentRecordingFile[64] = "";
unsigned long recordedFrames = 0;
unsigned long recordingDurationMs = 0;
bool currentFileDownloaded = false;  // FIX: Track if current recording was downloaded

// ===================
// AUDIO PLAYBACK FEATURES (Option 3)
// ===================
// Audio storage for playback from SD via ESP-NOW
#define AUDIO_CHUNK_SIZE 200  // Max ESP-NOW payload is ~250 bytes
char audioPlaybackFile[64] = "";
bool audioPlaybackRequested = false;

// ESP-NOW peer (main ESP32 MAC address - update this!)
uint8_t mainESP32MAC[] = {0xB0, 0xCB, 0xD8, 0xC7, 0xC4, 0x6C}; // Main ESP32 MAC address

// Audio chunk message structure for ESP-NOW
typedef struct audio_chunk_msg {
  char header[4];      // "AUDI"
  uint16_t chunkNum;   // Chunk number
  uint16_t totalChunks; // Total chunks
  uint8_t data[AUDIO_CHUNK_SIZE]; // Audio data
  uint8_t dataLen;     // Actual data length in this chunk
} audio_chunk_msg;

audio_chunk_msg audioMsg;
bool espNowPeerAdded = false;

// MJPEG header for AVI files
const uint8_t AVI_HEADER[] = {
  0x52, 0x49, 0x46, 0x46, // RIFF
  0x00, 0x00, 0x00, 0x00, // File size (updated later)
  0x41, 0x56, 0x49, 0x20, // AVI 
  0x4C, 0x49, 0x53, 0x54, // LIST
  0x44, 0x00, 0x00, 0x00, // List size
  0x68, 0x64, 0x72, 0x6C, // hdrl
  0x61, 0x76, 0x69, 0x68, // avih
  0x38, 0x00, 0x00, 0x00  // avih size
  // ... (simplified - we'll use a simpler MJPEG approach)
};

void OnDataRecv(const esp_now_recv_info *info, const uint8_t *incomingDataRaw, int len) {
  memcpy(&incomingData, incomingDataRaw, sizeof(incomingData));
  
  static unsigned long lastRecordStart = 0;
  const unsigned long MIN_RECORD_DURATION = 1000; // 1 second minimum
  
  if (incomingData.record || strcmp(incomingData.command, "RECORD") == 0) {
    recordingRequested = true;
    lastRecordStart = millis();
    Serial.println("[ESP-NOW] RECORD");
  } else if (strcmp(incomingData.command, "STOP") == 0) {
    if (millis() - lastRecordStart < MIN_RECORD_DURATION && isRecording) {
      return; // Ignore if too soon
    }
    recordingRequested = false;
    Serial.println("[ESP-NOW] STOP");
  }
}

// ===================
// AI Thinker Camera Pin Definitions
// ===================
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

// ===================
// HTTP Server Configuration
// ===================
#define PART_BOUNDARY "123456789000000000000987654321"

static const char* _STREAM_CONTENT_TYPE = "multipart/x-mixed-replace;boundary=" PART_BOUNDARY;
static const char* _STREAM_BOUNDARY = "\r\n--" PART_BOUNDARY "\r\n";
static const char* _STREAM_PART = "Content-Type: image/jpeg\r\nContent-Length: %u\r\nX-Recording: %d\r\n\r\n";

httpd_handle_t stream_httpd = NULL;
httpd_handle_t camera_httpd = NULL;

// ===================
// Serial Command Handler
// ===================
void handleSerialCommands() {
  if (Serial.available()) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    command.toUpperCase();

    Serial.printf("Serial command received: %s\n", command.c_str());

    if (command == "RECORD" || command == "REC" || command == "START") {
      recordingRequested = true;
      Serial.println("Recording triggered via Serial!");
    }
    else if (command == "STOP" || command == "END") {
      recordingRequested = false;
      Serial.println("Recording stop requested via Serial!");
    }
    else if (command == "STATUS") {
      Serial.printf("Status - Recording: %s, Requested: %s, Uptime: %lu ms\n",
                    isRecording ? "YES" : "NO",
                    recordingRequested ? "YES" : "NO",
                    millis());
    }
    else if (command == "HELP") {
      Serial.println("Available commands:");
      Serial.println("  RECORD, REC, START - Start recording indication");
      Serial.println("  STOP, END          - Stop recording indication");
      Serial.println("  STATUS             - Show current status");
      Serial.println("  HELP               - Show this help");
    }
    else {
      Serial.printf("Unknown command: %s (type HELP for available commands)\n", command.c_str());
    }
  }
}

// ===================
// Stream Handler (Based on working CameraWebServer)
// ===================
static esp_err_t stream_handler(httpd_req_t *req) {
  camera_fb_t * fb = NULL;
  esp_err_t res = ESP_OK;
  size_t _jpg_buf_len = 0;
  uint8_t * _jpg_buf = NULL;
  char part_buf[128];  // Increased buffer size like working code

  res = httpd_resp_set_type(req, _STREAM_CONTENT_TYPE);
  if(res != ESP_OK){
    return res;
  }

  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  httpd_resp_set_hdr(req, "X-Framerate", "60");  // Added from working code

  Serial.println("Client connected to stream");

  while(true){
    fb = esp_camera_fb_get();
    if (!fb) {
      Serial.println("Camera capture failed");
      res = ESP_FAIL;
    } else {
      if(fb->format != PIXFORMAT_JPEG){
        bool jpeg_converted = frame2jpg(fb, 80, &_jpg_buf, &_jpg_buf_len);
        esp_camera_fb_return(fb);
        fb = NULL;
        if(!jpeg_converted){
          Serial.println("JPEG compression failed");
          res = ESP_FAIL;
        }
      } else {
        _jpg_buf_len = fb->len;
        _jpg_buf = fb->buf;
      }
    }

    if(res == ESP_OK){
      res = httpd_resp_send_chunk(req, _STREAM_BOUNDARY, strlen(_STREAM_BOUNDARY));
    }
    if(res == ESP_OK){
      size_t hlen = snprintf((char *)part_buf, 128, _STREAM_PART, _jpg_buf_len, recordingRequested ? 1 : 0);
      res = httpd_resp_send_chunk(req, (const char *)part_buf, hlen);
    }
    if(res == ESP_OK){
      res = httpd_resp_send_chunk(req, (const char *)_jpg_buf, _jpg_buf_len);
    }

    if(fb){
      esp_camera_fb_return(fb);
      fb = NULL;
      _jpg_buf = NULL;
    } else if(_jpg_buf){
      free(_jpg_buf);
      _jpg_buf = NULL;
    }

    if(res != ESP_OK){
      Serial.println("Client disconnected from stream");
      break;
    }

    // FIX: Add small delay to allow main loop to process recording/other tasks
    delay(10);
  }

  return res;
}

// ===================
// Control Handler (HTTP API)
// ===================
static esp_err_t control_handler(httpd_req_t *req) {
  char*  buf;
  size_t buf_len;
  char command[32] = {0};
  
  buf_len = httpd_req_get_url_query_len(req) + 1;
  if (buf_len > 1) {
    buf = (char*)malloc(buf_len);
    if(!buf){
      httpd_resp_send_500(req);
      return ESP_FAIL;
    }
    if (httpd_req_get_url_query_str(req, buf, buf_len) == ESP_OK) {
      httpd_query_key_value(buf, "cmd", command, sizeof(command));
    }
    free(buf);
  }

  String response = "{\"status\":\"ok\",\"recording\":";
  
  if (strlen(command) > 0) {
    String cmd = String(command);
    cmd.toUpperCase();
    if (cmd == "RECORD" || cmd == "START") {
      recordingRequested = true;
      Serial.println("Recording triggered via HTTP!");
    } else if (cmd == "STOP" || cmd == "END") {
      recordingRequested = false;
      Serial.println("Recording stop requested via HTTP!");
    }
  }
  
  response += recordingRequested ? "true" : "false";
  response += ",\"uptime\":";
  response += millis();
  response += "}";

  httpd_resp_set_type(req, "application/json");
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  httpd_resp_send(req, response.c_str(), response.length());
  return ESP_OK;
}

// ===================
// Status Handler
// ===================
static esp_err_t status_handler(httpd_req_t *req) {
  // Get current file size if available
  unsigned long currentFileSize = 0;
  if (strlen(currentRecordingFile) > 0 && !isRecording) {
    File f = SD_MMC.open(currentRecordingFile, FILE_READ);
    if (f) {
      currentFileSize = f.size();
      f.close();
    }
  }
  
  String response = "{";
  response += "\"recording_requested\":" + String(recordingRequested ? "true" : "false") + ",";
  response += "\"recording_active\":" + String(isRecording ? "true" : "false") + ",";
  response += "\"sd_card_available\":" + String(sdCardAvailable ? "true" : "false") + ",";
  response += "\"frames_recorded\":" + String(recordedFrames) + ",";
  response += "\"current_file\":\"" + String(currentRecordingFile) + "\",";
  response += "\"current_file_size\":" + String(currentFileSize) + ",";
  response += "\"file_downloaded\":" + String(currentFileDownloaded ? "true" : "false") + ",";
  response += "\"uptime\":" + String(millis()) + ",";
  response += "\"free_heap\":" + String(ESP.getFreeHeap()) + ",";
  response += "\"stream_url\":\"http://" + WiFi.localIP().toString() + ":81/stream\",";
  response += "\"download_url\":\"http://" + WiFi.localIP().toString() + ":81/download\"";
  response += "}";
  
  httpd_resp_set_type(req, "application/json");
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  httpd_resp_send(req, response.c_str(), response.length());
  return ESP_OK;
}

// ===================
// Root Handler
// ===================
static esp_err_t root_handler(httpd_req_t *req) {
  String html = R"rawliteral(
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ESP32-CAM Stream</title>
    <style>
        body { font-family: Arial, sans-serif; text-align: center; background: #1a1a1a; color: white; }
        img { max-width: 100%; border: 2px solid #333; }
        .controls { margin: 20px; }
        button { padding: 15px 30px; margin: 5px; font-size: 16px; cursor: pointer; border: none; border-radius: 5px; }
        .record { background: #d32f2f; color: white; }
        .stop { background: #388e3c; color: white; }
        .recording { animation: pulse 1s infinite; }
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
        #status { margin: 10px; padding: 10px; background: #333; border-radius: 5px; }
    </style>
</head>
<body>
    <h1>ESP32-CAM Stream</h1>
    <div id="status">Loading...</div>
    <img id="stream" src="/stream" alt="Stream">
    <div class="controls">
        <button class="record" onclick="control('record')">Record</button>
        <button class="stop" onclick="control('stop')">Stop</button>
    </div>
    <script>
        function control(cmd) {
            fetch('/control?cmd=' + cmd)
                .then(r => r.json())
                .then(data => updateStatus(data));
        }
        function updateStatus(data) {
            const statusDiv = document.getElementById('status');
            statusDiv.textContent = 'Recording: ' + (data.recording ? 'YES' : 'NO') + ' | Uptime: ' + data.uptime + 'ms';
            if(data.recording) {
                statusDiv.classList.add('recording');
                statusDiv.style.background = '#d32f2f';
            } else {
                statusDiv.classList.remove('recording');
                statusDiv.style.background = '#333';
            }
        }
        setInterval(() => fetch('/status').then(r => r.json()).then(updateStatus), 1000);
    </script>
</body>
</html>
)rawliteral";

  httpd_resp_set_type(req, "text/html");
  httpd_resp_send(req, html.c_str(), html.length());
  return ESP_OK;
}

// ===================
// AUDIO HANDLERS (Option 3)
// ===================

// Handler to receive audio from laptop and save to SD card
static esp_err_t audio_upload_handler(httpd_req_t *req) {
  if (!sdCardAvailable) {
    httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR, "SD Card not available");
    return ESP_FAIL;
  }
  
  // Get filename from query string
  char filename[64] = "/audio_playback.wav";
  char query[128];
  if (httpd_req_get_url_query_str(req, query, sizeof(query)) == ESP_OK) {
    char fname[32];
    if (httpd_query_key_value(query, "file", fname, sizeof(fname)) == ESP_OK) {
      snprintf(filename, sizeof(filename), "/recordings/%s", fname);
    }
  }
  
  // Open file for writing
  File audioFile = SD_MMC.open(filename, FILE_WRITE);
  if (!audioFile) {
    httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR, "Cannot create audio file");
    return ESP_FAIL;
  }
  
  Serial.printf("[Audio Upload] Receiving audio to: %s\n", filename);
  
  // Receive data in chunks
  char buffer[1024];
  int received = 0;
  int totalReceived = 0;
  
  while ((received = httpd_req_recv(req, buffer, sizeof(buffer))) > 0) {
    audioFile.write((uint8_t*)buffer, received);
    totalReceived += received;
  }
  
  audioFile.close();
  
  // Save filename for playback
  strncpy(audioPlaybackFile, filename, sizeof(audioPlaybackFile) - 1);
  audioPlaybackFile[sizeof(audioPlaybackFile) - 1] = '\0';
  
  Serial.printf("[Audio Upload] Received %d bytes\n", totalReceived);
  
  // Send response
  httpd_resp_set_type(req, "application/json");
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  char response[128];
  snprintf(response, sizeof(response), "{\"status\":\"ok\",\"bytes\":%d,\"file\":\"%s\"}", totalReceived, filename);
  httpd_resp_send(req, response, strlen(response));
  
  return ESP_OK;
}

// Handler to trigger audio playback via ESP-NOW
static esp_err_t audio_play_handler(httpd_req_t *req) {
  if (strlen(audioPlaybackFile) == 0) {
    httpd_resp_send_err(req, HTTPD_404_NOT_FOUND, "No audio file uploaded");
    return ESP_FAIL;
  }
  
  if (!espNowPeerAdded) {
    httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR, "ESP-NOW peer not configured");
    return ESP_FAIL;
  }
  
  // Trigger playback in main loop
  audioPlaybackRequested = true;
  
  Serial.printf("[Audio Play] Will stream: %s\n", audioPlaybackFile);
  
  httpd_resp_set_type(req, "application/json");
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  httpd_resp_send(req, "{\"status\":\"playing\"}", HTTPD_RESP_USE_STRLEN);
  
  return ESP_OK;
}

// Function to stream audio file via ESP-NOW
void streamAudioViaESPNow() {
  if (strlen(audioPlaybackFile) == 0) {
    Serial.println("[Audio Stream] No file to play");
    audioPlaybackRequested = false;
    return;
  }
  
  File audioFile = SD_MMC.open(audioPlaybackFile, FILE_READ);
  if (!audioFile) {
    Serial.println("[Audio Stream] Cannot open audio file");
    audioPlaybackRequested = false;
    return;
  }
  
  size_t fileSize = audioFile.size();
  uint16_t totalChunks = (fileSize + AUDIO_CHUNK_SIZE - 1) / AUDIO_CHUNK_SIZE;
  
  Serial.printf("[Audio Stream] Streaming %lu bytes in %d chunks\n", fileSize, totalChunks);
  
  // Send START command
  strcpy(audioMsg.header, "STAR");
  audioMsg.chunkNum = 0;
  audioMsg.totalChunks = totalChunks;
  audioMsg.dataLen = 0;
  esp_now_send(mainESP32MAC, (uint8_t*)&audioMsg, sizeof(audioMsg));
  delay(100); // Give main ESP32 time to prepare
  
  // Stream audio chunks
  uint16_t chunkNum = 0;
  while (audioFile.available()) {
    size_t bytesRead = audioFile.read(audioMsg.data, AUDIO_CHUNK_SIZE);
    if (bytesRead == 0) break;
    
    strcpy(audioMsg.header, "AUDI");
    audioMsg.chunkNum = chunkNum;
    audioMsg.totalChunks = totalChunks;
    audioMsg.dataLen = bytesRead;
    
    esp_err_t result = esp_now_send(mainESP32MAC, (uint8_t*)&audioMsg, sizeof(audioMsg));
    if (result != ESP_OK) {
      Serial.printf("[Audio Stream] Send failed: %d\n", result);
    }
    
    chunkNum++;
    
    // Small delay to prevent overwhelming ESP-NOW
    if (chunkNum % 10 == 0) {
      delay(5);
    }
    
    // Progress every 50 chunks
    if (chunkNum % 50 == 0) {
      Serial.printf("[Audio Stream] Sent chunk %d/%d\n", chunkNum, totalChunks);
    }
  }
  
  audioFile.close();
  
  // Send END command
  delay(100);
  strcpy(audioMsg.header, "ENDA");
  audioMsg.chunkNum = chunkNum;
  audioMsg.dataLen = 0;
  esp_now_send(mainESP32MAC, (uint8_t*)&audioMsg, sizeof(audioMsg));
  
  Serial.println("[Audio Stream] Complete");
  audioPlaybackRequested = false;
}

// ===================
// Server Configuration
// ===================
void startCameraServer() {
  httpd_config_t config = HTTPD_DEFAULT_CONFIG();
  config.max_uri_handlers = 16;
  config.stack_size = 8192;        // FIX: Increase stack size (was 4096)
  config.max_open_sockets = 4;     // FIX: Limit concurrent connections
  config.lru_purge_enable = true;  // FIX: Enable socket purge on overflow
  config.server_port = 80;
  config.ctrl_port = 32768;

  httpd_uri_t index_uri = {
    .uri       = "/",
    .method    = HTTP_GET,
    .handler   = root_handler,
    .user_ctx  = NULL
  };

  httpd_uri_t status_uri = {
    .uri       = "/status",
    .method    = HTTP_GET,
    .handler   = status_handler,
    .user_ctx  = NULL
  };

  httpd_uri_t control_uri = {
    .uri       = "/control",
    .method    = HTTP_GET,
    .handler   = control_handler,
    .user_ctx  = NULL
  };

  // Audio upload endpoint
  httpd_uri_t audio_upload_uri = {
    .uri       = "/audio_upload",
    .method    = HTTP_POST,
    .handler   = audio_upload_handler,
    .user_ctx  = NULL
  };
  
  // Audio play endpoint
  httpd_uri_t audio_play_uri = {
    .uri       = "/audio_play",
    .method    = HTTP_GET,
    .handler   = audio_play_handler,
    .user_ctx  = NULL
  };

  if (httpd_start(&camera_httpd, &config) == ESP_OK) {
    httpd_register_uri_handler(camera_httpd, &index_uri);
    httpd_register_uri_handler(camera_httpd, &status_uri);
    httpd_register_uri_handler(camera_httpd, &control_uri);
    httpd_register_uri_handler(camera_httpd, &audio_upload_uri);
    httpd_register_uri_handler(camera_httpd, &audio_play_uri);
    Serial.println("HTTP server started on port 80");
    Serial.println("Audio endpoints: /audio_upload (POST), /audio_play (GET)");
  }

  config.server_port = 81;
  config.ctrl_port = 32769;
  // Keep increased stack size for download server

  httpd_uri_t stream_uri = {
    .uri       = "/stream",
    .method    = HTTP_GET,
    .handler   = stream_handler,
    .user_ctx  = NULL
  };

  httpd_uri_t download_uri = {
    .uri       = "/download",
    .method    = HTTP_GET,
    .handler   = download_handler,
    .user_ctx  = NULL
  };

  if (httpd_start(&stream_httpd, &config) == ESP_OK) {
    httpd_register_uri_handler(stream_httpd, &stream_uri);
    httpd_register_uri_handler(stream_httpd, &download_uri);
    Serial.println("Stream server started on port 81");
    Serial.println("Download endpoint: /download");
  }
}

// ===================
// Download Handler (for retrieving recorded video)
// ===================
static esp_err_t download_handler(httpd_req_t *req) {
  if (!sdCardAvailable) {
    httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR, "SD Card not available");
    return ESP_FAIL;
  }
  
  // Check if currently recording - if so, return error
  if (isRecording) {
    httpd_resp_set_status(req, "503 Service Unavailable");
    httpd_resp_set_type(req, "text/plain");
    httpd_resp_send(req, "Recording in progress, try again later", HTTPD_RESP_USE_STRLEN);
    return ESP_FAIL;
  }
  
  // FIX: Only serve the CURRENT recording file, not any old file
  if (strlen(currentRecordingFile) == 0) {
    httpd_resp_send_err(req, HTTPD_404_NOT_FOUND, "No recording made this session");
    return ESP_FAIL;
  }
  
  // Check if already downloaded
  if (currentFileDownloaded) {
    httpd_resp_send_err(req, HTTPD_404_NOT_FOUND, "Video already downloaded");
    return ESP_FAIL;
  }
  
  // Open the specific file from current recording
  File videoFile = SD_MMC.open(currentRecordingFile, FILE_READ);
  
  if (!videoFile) {
    httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR, "Cannot open video file");
    return ESP_FAIL;
  }
  
  size_t fileSize = videoFile.size();
  Serial.printf("[Download] Serving: %s (%lu bytes)\n", currentRecordingFile, fileSize);
  
  // Reject files that are too small (likely corrupted)
  if (fileSize < 1024) {
    Serial.println("[Download] File too small, likely corrupted");
    videoFile.close();
    return ESP_FAIL;
  }
  
  // FIX: Use char buffer for Content-Length
  char contentLengthStr[16];
  snprintf(contentLengthStr, sizeof(contentLengthStr), "%lu", fileSize);
  
  // FIX: Use char buffer for Content-Disposition
  char dispositionStr[128];
  String fileNameOnly = String(currentRecordingFile).substring(String(currentRecordingFile).lastIndexOf('/') + 1);
  snprintf(dispositionStr, sizeof(dispositionStr), "attachment; filename=\"%s\"", fileNameOnly.c_str());
  
  // Set headers
  httpd_resp_set_type(req, "video/x-motion-jpeg");
  httpd_resp_set_hdr(req, "Content-Disposition", dispositionStr);
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  httpd_resp_set_hdr(req, "Content-Length", contentLengthStr);
  // FIX: Add keep-alive header to prevent connection close
  httpd_resp_set_hdr(req, "Connection", "keep-alive");
  
  // Send file in chunks (smaller buffer to prevent stack overflow)
  uint8_t buffer[512];  // FIX: Further reduced from 1024 to 512 for stability
  size_t totalSent = 0;
  int chunkCount = 0;
  
  while (videoFile.available()) {
    size_t bytesRead = videoFile.read(buffer, sizeof(buffer));
    if (bytesRead > 0) {
      esp_err_t res = httpd_resp_send_chunk(req, (const char*)buffer, bytesRead);
      if (res != ESP_OK) {
        Serial.printf("[Download] Send failed at byte %lu (error: %d)\n", totalSent, res);
        videoFile.close();
        // Don't return error here - partial download is better than nothing
        httpd_resp_send_chunk(req, NULL, 0);
        return ESP_OK;
      }
      totalSent += bytesRead;
      chunkCount++;
      
      // Print progress every 100 chunks
      if (chunkCount % 100 == 0) {
        Serial.printf("[Download] Progress: %lu/%lu bytes\n", totalSent, fileSize);
      }
    }
    
    // FIX: Longer delay every 10 chunks to prevent WiFi overload
    if (chunkCount % 10 == 0) {
      delay(2);
    }
    yield();  // Allow WiFi stack to process
  }
  
  videoFile.close();
  httpd_resp_send_chunk(req, NULL, 0);  // End response
  
  Serial.printf("[Download] Sent %lu/%lu bytes successfully\n", totalSent, fileSize);
  
  // FIX: Mark as downloaded if 90% or more received
  if (totalSent >= fileSize * 0.9) {
    currentFileDownloaded = true;
    Serial.println("[Download] File marked as downloaded");
  } else {
    Serial.println("[Download] Partial download, can retry");
  }
  
  return ESP_OK;
}

// ===================
// Setup
// ===================
void setup() {
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);
  
  Serial.begin(115200);
  Serial.setDebugOutput(true);
  Serial.println();
  Serial.println("===================================");
  Serial.println("ESP32-CAM Stream Server Starting...");
  Serial.println("===================================");

  // Camera configuration (replicating working CameraWebServer structure)
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.frame_size = FRAMESIZE_UXGA;        // Start with UXGA like working code
  config.pixel_format = PIXFORMAT_JPEG;      // for streaming
  config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
  config.fb_location = CAMERA_FB_IN_PSRAM;
  config.jpeg_quality = 12;
  config.fb_count = 1;

  // if PSRAM IC present, init with UXGA resolution and higher JPEG quality
  if (psramFound()) {
    config.jpeg_quality = 10;
    config.fb_count = 2;
    config.grab_mode = CAMERA_GRAB_LATEST;
    Serial.println("PSRAM found - using optimized settings");
  } else {
    // Limit the frame size when PSRAM is not available
    config.frame_size = FRAMESIZE_SVGA;
    config.fb_location = CAMERA_FB_IN_DRAM;
    Serial.println("No PSRAM - using SVGA resolution");
  }

  // Initialize camera
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x\n", err);
    delay(1000);
    ESP.restart();
  }

  // Get sensor and adjust settings (like working code)
  sensor_t * s = esp_camera_sensor_get();
  // initial sensors are flipped vertically and colors are a bit saturated
  if (s->id.PID == OV3660_PID) {
    s->set_vflip(s, 1);        // flip it back
    s->set_brightness(s, 1);   // up the brightness just a bit
    s->set_saturation(s, -2);  // lower the saturation
  }
  // drop down frame size for higher initial frame rate
  s->set_framesize(s, FRAMESIZE_QVGA);  // Start with QVGA for better performance

  Serial.println("Camera initialized successfully");

  // Configure WiFi with DHCP (automatic IP assignment)
  WiFi.begin(ssid, password);
  WiFi.setSleep(false);  // Important for streaming stability

  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();

  Serial.println("===================================");
  Serial.println("WiFi Connected!");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());
  Serial.print("MAC Address: ");
  Serial.println(WiFi.macAddress());
  Serial.print("Stream URL: http://");
  Serial.print(WiFi.localIP().toString());
  Serial.println(":81/stream");
  Serial.print("Web Interface: http://");
  Serial.println(WiFi.localIP().toString());
  Serial.println("===================================");
  Serial.println("IMPORTANT: Use this MAC for main_firmware:");
  Serial.println(WiFi.macAddress());
  Serial.println("===================================");

  // Initialize ESP-NOW
  if (esp_now_init() != ESP_OK) {
    Serial.println("ESP-NOW initialization failed!");
  } else {
    Serial.println("ESP-NOW initialized successfully");
    esp_now_register_recv_cb(OnDataRecv);
    
    // Add peer for audio playback (main ESP32)
    // NOTE: You must update mainESP32MAC with your main ESP32's MAC address!
    esp_now_peer_info_t peerInfo = {};
    memcpy(peerInfo.peer_addr, mainESP32MAC, 6);
    peerInfo.channel = 0;
    peerInfo.encrypt = false;
    if (esp_now_add_peer(&peerInfo) == ESP_OK) {
      espNowPeerAdded = true;
      Serial.println("ESP-NOW peer added for audio playback");
    } else {
      Serial.println("WARNING: Failed to add ESP-NOW peer for audio");
    }
  }

  // Initialize SD Card
  initSDCard();

  // Start servers
  startCameraServer();

  Serial.println();
  Serial.println("Serial commands:");
  Serial.println("  RECORD/REC/START - Start recording indication");
  Serial.println("  STOP/END         - Stop recording indication");
  Serial.println("  STATUS           - Show current status");
  Serial.println("  HELP             - Show help");
  Serial.println("===================================");
}

// ===================
// SD Card Functions
// ===================
void initSDCard() {
  Serial.println("\n===================================");
  Serial.println("Initializing SD Card...");
  
  // SD_MMC uses specific pins on ESP32-CAM
  if (!SD_MMC.begin()) {
    Serial.println("SD Card Mount Failed!");
    sdCardAvailable = false;
    return;
  }
  
  uint8_t cardType = SD_MMC.cardType();
  if (cardType == CARD_NONE) {
    Serial.println("No SD Card attached!");
    sdCardAvailable = false;
    return;
  }
  
  sdCardAvailable = true;
  
  Serial.print("SD Card Type: ");
  if (cardType == CARD_MMC) {
    Serial.println("MMC");
  } else if (cardType == CARD_SD) {
    Serial.println("SDSC");
  } else if (cardType == CARD_SDHC) {
    Serial.println("SDHC");
  } else {
    Serial.println("UNKNOWN");
  }
  
  uint64_t cardSize = SD_MMC.cardSize() / (1024 * 1024);
  Serial.printf("SD Card Size: %lluMB\n", cardSize);
  
  // Create recordings directory if it doesn't exist
  if (!SD_MMC.exists("/recordings")) {
    SD_MMC.mkdir("/recordings");
    Serial.println("Created /recordings directory");
  }
  
  Serial.println("SD Card initialized successfully!");
  Serial.println("===================================\n");
}

String getNextFileName() {
  static int fileIndex = 0;
  char filename[64];

  // FIX: Don't check file existence - just use incrementing counter
  // This is much faster than SD_MMC.exists() which is very slow
  snprintf(filename, sizeof(filename), "/recordings/rec_%03d.mjpeg", fileIndex++);

  return String(filename);
}

bool startSDRecording() {
  if (!sdCardAvailable) {
    Serial.println("ERROR: SD Card not available!");
    return false;
  }

  if (mjpegFile) {
    mjpegFile.close();
  }

  String filename = getNextFileName();
  strncpy(currentRecordingFile, filename.c_str(), sizeof(currentRecordingFile) - 1);
  currentRecordingFile[sizeof(currentRecordingFile) - 1] = '\0';

  mjpegFile = SD_MMC.open(filename, FILE_WRITE);
  if (!mjpegFile) {
    Serial.printf("ERROR: Failed to open file: %s\n", filename.c_str());
    return false;
  }

  recordedFrames = 0;
  recordingDurationMs = 0;
  currentFileDownloaded = false;

  Serial.printf("[SD Record] Started: %s\n", filename.c_str());
  return true;
}

void stopSDRecording() {
  if (mjpegFile) {
    // FIX: Sync and flush before closing
    mjpegFile.flush();
    SD_MMC.end();
    SD_MMC.begin();
    
    // Get actual file size
    File checkFile = SD_MMC.open(currentRecordingFile, FILE_READ);
    unsigned long actualSize = checkFile ? checkFile.size() : 0;
    if (checkFile) checkFile.close();
    
    mjpegFile.close();
    recordingDurationMs = millis() - recordingStartTime;
    
    // Calculate actual frame rate
    float fps = (recordingDurationMs > 0) ? (recordedFrames * 1000.0 / recordingDurationMs) : 0;
    
    Serial.printf("[SD Record] Saved: %lu frames, %.1f KB, %lu ms (%.1f fps)\n", 
                  recordedFrames, actualSize/1024.0, recordingDurationMs, fps);
  }
}

void recordFrameToSD(camera_fb_t* fb) {
  if (!mjpegFile || !fb) return;

  static unsigned long lastFrameTime = 0;

  // FIX: Maintain consistent 15 fps (66ms between frames)
  unsigned long now = millis();
  unsigned long elapsed = now - lastFrameTime;
  if (elapsed < 66) {
    delay(66 - elapsed);
  }
  lastFrameTime = millis();

  // Write frame and flush to SD
  size_t written = mjpegFile.write(fb->buf, fb->len);
  mjpegFile.flush();

  if (written == fb->len) {
    recordedFrames++;
  }
}

// ===================
// Main Loop
// ===================
void loop() {
  handleSerialCommands();
  
  // Handle audio playback request (Option 3)
  if (audioPlaybackRequested) {
    streamAudioViaESPNow();
  }
  
  // Minimum recording duration (prevents accidental quick stops)
  static unsigned long recordStartTime = 0;
  const unsigned long MIN_RECORD_MS = 1000; // 1 second minimum
  
  // Handle recording state changes
  if (recordingRequested != isRecording) {
    // Block stop if too soon
    if (isRecording && !recordingRequested) {
      if (millis() - recordStartTime < MIN_RECORD_MS) {
        recordingRequested = true;
        return;
      }
    }
    
    isRecording = recordingRequested;
    if (isRecording) {
      recordStartTime = millis();
      recordingStartTime = millis();
      startSDRecording();
      Serial.println("RECORDING STARTED");
    } else {
      stopSDRecording();
      Serial.println("RECORDING STOPPED");
    }
  }
  
  // If recording to SD, capture frames
  if (isRecording && sdCardAvailable) {
    camera_fb_t* fb = esp_camera_fb_get();
    if (fb) {
      recordFrameToSD(fb);
      esp_camera_fb_return(fb);
    }
  } else if (isRecording && !sdCardAvailable) {
    static unsigned long lastSdWarning = 0;
    if (millis() - lastSdWarning > 1000) {
      Serial.println("[ERROR] Recording requested but SD card not available!");
      lastSdWarning = millis();
    }
  }

  // Periodic status
  static unsigned long lastStatusTime = 0;
  if (millis() - lastStatusTime > 10000) {
    Serial.printf("[Status] Rec: %s, Frames: %lu\n", 
                  isRecording ? "YES" : "NO", recordedFrames);
    lastStatusTime = millis();
  }

  // Keep WiFi connection alive
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi disconnected, reconnecting...");
    WiFi.reconnect();
  }

  delay(10);
}
