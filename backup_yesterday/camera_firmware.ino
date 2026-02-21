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

void OnDataRecv(const esp_now_recv_info *info, const uint8_t *incomingDataRaw, int len) {
  const uint8_t *mac = info->src_addr;
  memcpy(&incomingData, incomingDataRaw, sizeof(incomingData));
  Serial.printf("ESP-NOW received from %02X:%02X:%02X:%02X:%02X:%02X\n",
                mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
  Serial.printf("Command: %s, Record: %d\n", incomingData.command, incomingData.record);
  
  if (incomingData.record || strcmp(incomingData.command, "RECORD") == 0) {
    recordingRequested = true;
    Serial.println("Recording triggered via ESP-NOW!");
  } else if (strcmp(incomingData.command, "STOP") == 0) {
    recordingRequested = false;
    Serial.println("Recording stop requested via ESP-NOW!");
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
  String response = "{";
  response += "\"recording_requested\":" + String(recordingRequested ? "true" : "false") + ",";
  response += "\"uptime\":" + String(millis()) + ",";
  response += "\"free_heap\":" + String(ESP.getFreeHeap()) + ",";
  response += "\"stream_url\":\"http://" + WiFi.localIP().toString() + ":81/stream\"";
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
// Server Configuration
// ===================
void startCameraServer() {
  httpd_config_t config = HTTPD_DEFAULT_CONFIG();
  config.max_uri_handlers = 16;  // Added from working code
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

  if (httpd_start(&camera_httpd, &config) == ESP_OK) {
    httpd_register_uri_handler(camera_httpd, &index_uri);
    httpd_register_uri_handler(camera_httpd, &status_uri);
    httpd_register_uri_handler(camera_httpd, &control_uri);
    Serial.println("HTTP server started on port 80");
  }

  config.server_port = 81;
  config.ctrl_port = 32769;

  httpd_uri_t stream_uri = {
    .uri       = "/stream",
    .method    = HTTP_GET,
    .handler   = stream_handler,
    .user_ctx  = NULL
  };

  if (httpd_start(&stream_httpd, &config) == ESP_OK) {
    httpd_register_uri_handler(stream_httpd, &stream_uri);
    Serial.println("Stream server started on port 81");
  }
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
  }

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
// Main Loop
// ===================
void loop() {
  handleSerialCommands();
  
  // Handle recording state changes
  if (recordingRequested != isRecording) {
    isRecording = recordingRequested;
    if (isRecording) {
      recordingStartTime = millis();
      Serial.println("=== RECORDING STARTED ===");
    } else {
      unsigned long duration = millis() - recordingStartTime;
      Serial.printf("=== RECORDING STOPPED (Duration: %lu ms) ===\n", duration);
    }
  }

  // Keep WiFi connection alive
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi disconnected, reconnecting...");
    WiFi.reconnect();
  }

  delay(10);
}
