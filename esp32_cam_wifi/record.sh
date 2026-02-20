#!/bin/bash
# ESP32-CAM Recording Script for Linux/macOS
# Two-pass approach: First record AVI (copy), then convert to MP4 with proper timing

ESP32_IP="10.42.0.82"
STREAM_URL="http://${ESP32_IP}:81/stream"
OUTPUT_DIR="recordings"

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Function to show usage
show_usage() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  live       - View live stream (ffplay)"
    echo "  record     - Start continuous recording (two-pass: AVI -> MP4)"
    echo "  quick      - Quick record with copy mode only (AVI format)"
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
    echo "  $0 quick"
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

# Convert AVI to MP4 with proper frame rate
convert_to_mp4() {
    local avi_file="$1"
    local mp4_file="${avi_file%.avi}.mp4"
    
    echo "Converting to MP4 with proper timing..."
    ffmpeg -hide_banner -loglevel error -i "$avi_file" \
        -c:v libx264 -preset ultrafast -crf 28 -r 15 -pix_fmt yuv420p \
        -movflags +faststart -y "$mp4_file"
    
    if [ $? -eq 0 ]; then
        rm -f "$avi_file"
        echo "✓ Saved: $(basename "$mp4_file")"
    else
        echo "✗ Conversion failed, keeping AVI: $(basename "$avi_file")"
    fi
}

case "$1" in
    live)
        echo "Opening live stream..."
        ffplay "$STREAM_URL"
        ;;
    
    quick)
        # Quick recording - just copy MJPEG stream to AVI (no timing fix)
        check_ffmpeg
        AVI_FILE="${OUTPUT_DIR}/quick_$(timestamp).avi"
        echo "Quick recording to: $(basename "$AVI_FILE")"
        echo "Press Ctrl+C to stop"
        
        ffmpeg -hide_banner -loglevel error -thread_queue_size 8192 \
            -i "$STREAM_URL" -c:v copy -f avi -y "$AVI_FILE"
        
        echo ""
        if [ -f "$AVI_FILE" ] && [ -s "$AVI_FILE" ]; then
            SIZE=$(du -h "$AVI_FILE" | cut -f1)
            echo "✓ Recording saved: $(basename "$AVI_FILE") ($SIZE)"
            echo "  Note: This is raw MJPEG. Video may play at wrong speed."
            echo "  Run: $0 convert $(basename "$AVI_FILE") to fix timing"
        fi
        ;;
    
    record)
        check_ffmpeg
        AVI_FILE="${OUTPUT_DIR}/recording_$(timestamp).avi"
        MP4_FILE="${AVI_FILE%.avi}.mp4"
        
        echo "Starting two-pass recording..."
        echo "  Pass 1: Recording raw stream to AVI"
        echo "  Output: $(basename "$AVI_FILE")"
        echo "Press Ctrl+C to stop"
        
        # Record to AVI with copy mode
        ffmpeg -hide_banner -loglevel error -thread_queue_size 8192 \
            -i "$STREAM_URL" -c:v copy -f avi -y "$AVI_FILE"
        
        echo ""
        if [ -f "$AVI_FILE" ] && [ -s "$AVI_FILE" ]; then
            # Convert to MP4 with proper timing
            convert_to_mp4 "$AVI_FILE"
        else
            echo "✗ Recording failed or empty"
        fi
        ;;
    
    segment)
        check_ffmpeg
        echo "Recording in 5-minute segments..."
        echo "Press Ctrl+C to stop"
        
        # Record in segments, converting each to MP4
        ffmpeg -hide_banner -loglevel error -thread_queue_size 8192 \
            -i "$STREAM_URL" -c:v copy -f avi -y "${OUTPUT_DIR}/temp_segment.avi" &
        FFMPEG_PID=$!
        
        # Wait for interrupt
        trap "kill $FFMPEG_PID 2>/dev/null; convert_to_mp4 '${OUTPUT_DIR}/temp_segment.avi'; exit 0" INT
        wait $FFMPEG_PID
        convert_to_mp4 "${OUTPUT_DIR}/temp_segment.avi"
        ;;
    
    timestamp)
        check_ffmpeg
        AVI_FILE="${OUTPUT_DIR}/recording_$(timestamp).avi"
        
        echo "Recording with timestamp..."
        echo "Press Ctrl+C to stop"
        
        ffmpeg -hide_banner -loglevel error -thread_queue_size 8192 \
            -i "$STREAM_URL" -c:v copy -f avi -y "$AVI_FILE"
        
        echo ""
        if [ -f "$AVI_FILE" ] && [ -s "$AVI_FILE" ]; then
            convert_to_mp4 "$AVI_FILE"
        fi
        ;;
    
    convert)
        # Convert existing AVI to MP4
        if [ -z "$2" ]; then
            echo "Usage: $0 convert <avi_filename>"
            exit 1
        fi
        AVI_FILE="${OUTPUT_DIR}/$2"
        if [ ! -f "$AVI_FILE" ]; then
            echo "File not found: $AVI_FILE"
            exit 1
        fi
        convert_to_mp4 "$AVI_FILE"
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
