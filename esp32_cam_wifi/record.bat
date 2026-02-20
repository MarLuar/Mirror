@echo off
REM ESP32-CAM Recording Script for Windows
REM Two-pass approach: First record AVI (copy), then convert to MP4 with proper timing

set ESP32_IP=10.42.0.82
set STREAM_URL=http://%ESP32_IP%:81/stream
set OUTPUT_DIR=recordings

REM Create output directory
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

REM Parse command
if /I "%1"=="live" goto :live
if /I "%1"=="record" goto :record
if /I "%1"=="quick" goto :quick
if /I "%1"=="timestamp" goto :timestamp
if /I "%1"=="status" goto :status
if /I "%1"=="record-on" goto :record-on
if /I "%1"=="start" goto :record-on
if /I "%1"=="record-off" goto :record-off
if /I "%1"=="stop" goto :record-off
if /I "%1"=="trigger" goto :trigger
if /I "%1"=="help" goto :help
if /I "%1"=="--help" goto :help
if /I "%1"=="-h" goto :help
if "%1"=="" goto :help

echo Unknown command: %1
goto :help

:live
echo Opening live stream...
ffplay "%STREAM_URL%"
goto :end

:quick
REM Quick recording - just copy MJPEG stream to AVI (no timing fix)
for /f "tokens=2 delims==" %%a in ('wmic OS Get localdatetime /value') do set "dt=%%a"
set "YYYY=%dt:~0,4%" & set "MM=%dt:~4,2%" & set "DD=%dt:~6,2%"
set "HH=%dt:~8,2%" & set "Min=%dt:~10,2%" & set "Sec=%dt:~12,2%"
set "AVI_FILE=%OUTPUT_DIR%\quick_%YYYY%%MM%%DD%_%HH%%Min%%Sec%.avi"

echo Quick recording to: %AVI_FILE%
echo Press Ctrl+C to stop

ffmpeg -hide_banner -loglevel error -thread_queue_size 8192 -i "%STREAM_URL%" -c:v copy -f avi -y "%AVI_FILE%"

echo.
if exist "%AVI_FILE%" (
    echo ✓ Recording saved: %AVI_FILE%
    echo   Note: This is raw MJPEG. Video may play at wrong speed.
) else (
    echo ✗ Recording failed
)
goto :end

:record
REM Two-pass recording: AVI first, then convert to MP4
for /f "tokens=2 delims==" %%a in ('wmic OS Get localdatetime /value') do set "dt=%%a"
set "YYYY=%dt:~0,4%" & set "MM=%dt:~4,2%" & set "DD=%dt:~6,2%"
set "HH=%dt:~8,2%" & set "Min=%dt:~10,2%" & set "Sec=%dt:~12,2%"
set "AVI_FILE=%OUTPUT_DIR%\recording_%YYYY%%MM%%DD%_%HH%%Min%%Sec%.avi"
set "MP4_FILE=%OUTPUT_DIR%\recording_%YYYY%%MM%%DD%_%HH%%Min%%Sec%.mp4"

echo Starting two-pass recording...
echo   Pass 1: Recording raw stream to AVI
echo   Output: %AVI_FILE%
echo Press Ctrl+C to stop

ffmpeg -hide_banner -loglevel error -thread_queue_size 8192 -i "%STREAM_URL%" -c:v copy -f avi -y "%AVI_FILE%"

echo.
if exist "%AVI_FILE%" (
    echo Converting to MP4 with proper timing...
    ffmpeg -hide_banner -loglevel error -i "%AVI_FILE%" -c:v libx264 -preset ultrafast -crf 28 -r 15 -pix_fmt yuv420p -movflags +faststart -y "%MP4_FILE%"
    
    if exist "%MP4_FILE%" (
        del "%AVI_FILE%"
        echo ✓ Saved: %MP4_FILE%
    ) else (
        echo ✗ Conversion failed, keeping AVI: %AVI_FILE%
    )
) else (
    echo ✗ Recording failed
)
goto :end

:timestamp
for /f "tokens=2 delims==" %%a in ('wmic OS Get localdatetime /value') do set "dt=%%a"
set "YYYY=%dt:~0,4%" & set "MM=%dt:~4,2%" & set "DD=%dt:~6,2%"
set "HH=%dt:~8,2%" & set "Min=%dt:~10,2%" & set "Sec=%dt:~12,2%"
set "AVI_FILE=%OUTPUT_DIR%\recording_%YYYY%%MM%%DD%_%HH%%Min%%Sec%.avi"

echo Recording to: %AVI_FILE%
echo Press Ctrl+C to stop

ffmpeg -hide_banner -loglevel error -thread_queue_size 8192 -i "%STREAM_URL%" -c:v copy -f avi -y "%AVI_FILE%"

echo.
if exist "%AVI_FILE%" (
    echo Converting to MP4...
    ffmpeg -hide_banner -loglevel error -i "%AVI_FILE%" -c:v libx264 -preset ultrafast -crf 28 -r 15 -pix_fmt yuv420p -movflags +faststart -y "%MP4_FILE%"
    if exist "%MP4_FILE%" del "%AVI_FILE%"
)
goto :end

:status
echo Checking ESP32-CAM status...
curl -s "http://%ESP32_IP%/status"
echo.
goto :end

:record-on
echo Sending record trigger...
curl "http://%ESP32_IP%/control?cmd=record"
echo.
goto :end

:record-off
echo Sending stop trigger...
curl "http://%ESP32_IP%/control?cmd=stop"
echo.
goto :end

:trigger
where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    if exist "record_triggered.py" (
        python record_triggered.py
    ) else (
        echo record_triggered.py not found!
        exit /b 1
    )
) else (
    echo Python not found! Please install Python.
    exit /b 1
)
goto :end

:help
echo Usage: %0 [command]
echo.
echo Commands:
echo   live       - View live stream (ffplay)
echo   record     - Start continuous recording (two-pass: AVI -^> MP4)
echo   quick      - Quick record with copy mode only (AVI format)
echo   timestamp  - Record with timestamp filename
echo   trigger    - Monitor and record based on trigger (Python)
echo   status     - Check ESP32-CAM status
echo   record-on  - Send HTTP record trigger
echo   record-off - Send HTTP stop trigger
echo   help       - Show this help
echo.
echo Examples:
echo   %0 live
echo   %0 record
echo   %0 quick

:end
