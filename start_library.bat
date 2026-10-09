@echo off
cd /d "%~dp0"
py --version >nul 2>nul
if errorlevel 1 (
 echo ERROR: Python launcher py was not found. Install Python first.
 pause
 exit /b 1
)
py -c "from operations import capture_port_busy; import sys; sys.exit(1 if capture_port_busy() else 0)"
if errorlevel 1 (
 echo Capture port 8877 is already occupied. No second proxy will be started.
) else (
 echo Starting capture in a separate window...
 start "IZZI Capture Proxy" "%ComSpec%" /c call "%~dp0capture_mode.bat"
)
start "" http://127.0.0.1:8765/
py server.py
pause
