#!/bin/bash
# ESP32-CAM Recording Script for Linux/macOS
# Simple bash script to record from ESP32-CAM stream

# ESP32-CAM IP Address (from Serial Monitor)
ESP32_IP="10.42.0.82"
STREAM_URL="http://${ESP32_IP}:81/stream"
OUTPUT_DIR="recordings"

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"

# Function to show usage
show_usage() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  live       - View live stream (ffplay)"
    echo "  record     - Start continuous recording"
    echo "  segment    - Record in 5-minute segments"
    echo "  timestamp  - Record with timestamp filename"
    echo "  trigger    - Monitor and record based on trigger"
    echo "  status     - Check ESP32-CAM status"
    echo "  record-on  - Send HTTP record trigger"
    echo "  record-off - Send HTTP stop trigger"
    echo "  help       - Show this help"
    echo ""
    echo "Examples:"
    echo "  $0 live"
    echo "  $0 record"
    echo "  $0 timestamp"
}

# Check if ffmpeg is installed
check_ffmpeg() {
    if ! command -v ffmpeg &> /dev/null; then
        echo "ERROR: ffmpeg is not installed!"
        echo "Install it with:"
        echo "  Ubuntu/Debian: sudo apt-get install ffmpeg"
        echo "  macOS: brew install ffmpeg"
        exit 1
    fi
}

# Generate timestamp
timestamp() {
    date +"%Y%m%d_%H%M%S"
}

case "$1" in
    live)
        check_ffmpeg
        echo "Opening live stream..."
        ffplay "$STREAM_URL"
        ;;
    
    record)
        check_ffmpeg
        OUTPUT="${OUTPUT_DIR}/recording_$(timestamp).mp4"
        echo "Starting continuous recording to: $OUTPUT"
        echo "Press Ctrl+C to stop"
        ffmpeg -hide_banner -loglevel error -fflags +discardcorrupt -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -thread_queue_size 4096 -i "$STREAM_URL" -c:v libx264 -preset ultrafast -tune zerolatency -crf 28 -r 15 -pix_fmt yuv420p -movflags +faststart -y "$OUTPUT"
        ;;
    
    segment)
        check_ffmpeg
        echo "Recording in 5-minute segments to: ${OUTPUT_DIR}/"
        echo "Press Ctrl+C to stop"
        ffmpeg -hide_banner -loglevel error -f mjpeg -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -thread_queue_size 512 -i "$STREAM_URL" \
            -c:v libx264 -preset superfast -crf 23 -r 15 -vf "fps=15,format=yuv420p" -vsync cfr -max_muxing_queue_size 1024 \
            -f segment -segment_time 300 -reset_timestamps 1 -strftime 1 \
            "${OUTPUT_DIR}/segment_%Y%m%d_%H%M%S.mp4"
        ;;
    
    timestamp)
        check_ffmpeg
        OUTPUT="${OUTPUT_DIR}/recording_$(timestamp).mp4"
        echo "Recording to: $OUTPUT"
        echo "Press Ctrl+C to stop"
        ffmpeg -hide_banner -loglevel error -fflags +discardcorrupt -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -thread_queue_size 4096 -i "$STREAM_URL" -c:v libx264 -preset ultrafast -tune zerolatency -crf 28 -r 15 -pix_fmt yuv420p -movflags +faststart -y "$OUTPUT"
        ;;
    
    trigger)
        if command -v python3 &> /dev/null; then
            if [ -f "record_triggered.py" ]; then
                python3 record_triggered.py
            else
                echo "record_triggered.py not found!"
                exit 1
            fi
        else
            echo "Python3 not found! Please install Python3."
            exit 1
        fi
        ;;
    
    status)
        echo "Checking ESP32-CAM status..."
        curl -s "http://${ESP32_IP}/status" | python3 -m json.tool 2>/dev/null || curl -s "http://${ESP32_IP}/status"
        echo ""
        ;;
    
    record-on|start)
        echo "Sending record trigger..."
        curl "http://${ESP32_IP}/control?cmd=record"
        echo ""
        ;;
    
    record-off|stop)
        echo "Sending stop trigger..."
        curl "http://${ESP32_IP}/control?cmd=stop"
        echo ""
        ;;
    
    help|--help|-h|"")
        show_usage
        ;;
    
    *)
        echo "Unknown command: $1"
        show_usage
        exit 1
        ;;
esac
