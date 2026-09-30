@echo off
cd /d "%~dp0"
echo IZZI Offline Library v3.3 - Capture Proxy
echo Proxy: 127.0.0.1:8877
where mitmdump >nul 2>nul
if errorlevel 1 (
 echo ERROR: mitmdump was not found. Run install_capture.bat first.
 pause
 exit /b 1
)
mitmdump -p 8877 -s capture_addon.py
echo Capture proxy stopped.
pause
