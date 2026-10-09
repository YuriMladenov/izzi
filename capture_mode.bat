@echo off
cd /d "%~dp0"
echo IZZI Offline Library v3.3 - Capture Proxy
echo Local proxy: 127.0.0.1:8877
echo LAN proxy: use this computer IPv4 address and port 8877.
echo Allow TCP 8877 in Windows Firewall for Private / LocalSubnet.
where mitmdump >nul 2>nul
if errorlevel 1 (
 echo ERROR: mitmdump was not found. Run install_capture.bat first.
 pause
 exit /b 1
)
mitmdump --listen-host 0.0.0.0 -p 8877 -s capture_addon.py
echo Capture proxy stopped.
pause
