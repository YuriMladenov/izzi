@echo off
cd /d "%~dp0"
if "%~1"=="" (echo Drag HAR files onto this BAT & pause & exit /b 1)
py import_har.py %*
pause
