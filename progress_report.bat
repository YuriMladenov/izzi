@echo off
cd /d "%~dp0"
py progress_report.py
set "IZZI_REPORT_RESULT=%ERRORLEVEL%"
pause
exit /b %IZZI_REPORT_RESULT%
