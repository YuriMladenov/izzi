@echo off
cd /d "%~dp0"
py missing_assets_report.py
set "IZZI_REPORT_RESULT=%ERRORLEVEL%"
pause
exit /b %IZZI_REPORT_RESULT%
