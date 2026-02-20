@echo off
REM ESP32-CAM Recording Script for Windows
REM Simple batch script to record from ESP32-CAM stream

REM ESP32-CAM IP Address (from Serial Monitor)
set ESP32_IP=10.42.0.82
set STREAM_URL=http://%ESP32_IP%:81/stream
set OUTPUT_DIR=recordings

REM Create output directory if it doesn't exist
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

REM Check if ffmpeg is installed
where ffmpeg >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: ffmpeg is not found in PATH!
    echo Please install ffmpeg from https://ffmpeg.org/download.html
    echo and add it to your system PATH.
    exit /b 1
)

REM Parse command
if /I "%1"=="live" goto :live
if /I "%1"=="record" goto :record
if /I "%1"=="segment" goto :segment
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

:record
for /f "tokens=2 delims==" %%a in ('wmic OS Get localdatetime /value') do set "dt=%%a"
set "YY=%dt:~2,2%" & set "YYYY=%dt:~0,4%" & set "MM=%dt:~4,2%" & set "DD=%dt:~6,2%"
set "HH=%dt:~8,2%" & set "Min=%dt:~10,2%" & set "Sec=%dt:~12,2%"
set "OUTPUT=%OUTPUT_DIR%\recording_%YYYY%%MM%%DD%_%HH%%Min%%Sec%.mp4"
echo Starting continuous recording to: %OUTPUT%
echo Press Ctrl+C to stop
ffmpeg -hide_banner -loglevel error -f mjpeg -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -thread_queue_size 512 -i "%STREAM_URL%" -c:v libx264 -preset superfast -crf 23 -r 15 -vf "fps=15,format=yuv420p" -vsync cfr -max_muxing_queue_size 1024 -movflags +faststart -y "%OUTPUT%"
goto :end

:segment
echo Recording in 5-minute segments to: %OUTPUT_DIR%\
echo Press Ctrl+C to stop
ffmpeg -hide_banner -loglevel error -f mjpeg -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -thread_queue_size 512 -i "%STREAM_URL%" -c:v libx264 -preset superfast -crf 23 -r 15 -vf "fps=15,format=yuv420p" -vsync cfr -max_muxing_queue_size 1024 -f segment -segment_time 300 -reset_timestamps 1 -strftime 1 "%OUTPUT_DIR%\segment_%%Y%%m%%d_%%H%%M%%S.mp4"
goto :end

:timestamp
for /f "tokens=2 delims==" %%a in ('wmic OS Get localdatetime /value') do set "dt=%%a"
set "YY=%dt:~2,2%" & set "YYYY=%dt:~0,4%" & set "MM=%dt:~4,2%" & set "DD=%dt:~6,2%"
set "HH=%dt:~8,2%" & set "Min=%dt:~10,2%" & set "Sec=%dt:~12,2%"
set "OUTPUT=%OUTPUT_DIR%\recording_%YYYY%%MM%%DD%_%HH%%Min%%Sec%.mp4"
echo Recording to: %OUTPUT%
echo Press Ctrl+C to stop
ffmpeg -hide_banner -loglevel error -f mjpeg -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -fflags +discardcorrupt+genpts -use_wallclock_as_timestamps 1 -i "%STREAM_URL%" -c:v libx264 -preset superfast -crf 18 -filter:v "setpts='N/(15*TB)',fps=15" -r 15 -pix_fmt yuv420p -y "%OUTPUT%"
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
echo   record     - Start continuous recording
echo   segment    - Record in 5-minute segments
echo   timestamp  - Record with timestamp filename
echo   trigger    - Monitor and record based on trigger (requires Python)
echo   status     - Check ESP32-CAM status
echo   record-on  - Send HTTP record trigger
echo   record-off - Send HTTP stop trigger
echo   help       - Show this help
echo.
echo Examples:
echo   %0 live
echo   %0 record
echo   %0 timestamp
goto :end

:end
