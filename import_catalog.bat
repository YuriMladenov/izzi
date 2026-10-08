@echo off
cd /d "%~dp0"
if "%~1"=="" (
  echo Drag the catalogue HAR file onto this BAT.
  pause
  exit /b 1
)
py import_catalog.py "%~1"
pause
