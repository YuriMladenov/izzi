@echo off
cd /d "%~dp0"
py --version >nul 2>nul
if errorlevel 1 (
 echo ERROR: Python launcher py was not found. Install Python first.
 pause
 exit /b 1
)
start "" http://127.0.0.1:8765/
py project_launcher.py
pause
