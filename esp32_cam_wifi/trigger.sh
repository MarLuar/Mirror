#!/bin/bash
# Quick trigger script for ESP32-CAM recording

# ESP32-CAM IP Address (from Serial Monitor)
ESP32_IP="10.42.0.82"

case "$1" in
    start|record|on)
        curl "http://${ESP32_IP}/control?cmd=record"
        echo ""
        ;;
    stop|off)
        curl "http://${ESP32_IP}/control?cmd=stop"
        echo ""
        ;;
    status)
        curl -s "http://${ESP32_IP}/status" | python3 -m json.tool
        ;;
    *)
        echo "Usage: $0 {start|stop|status}"
        exit 1
        ;;
esac
