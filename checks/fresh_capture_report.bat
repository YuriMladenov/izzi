@echo off
cd /d "%~dp0.."
py checks\fresh_capture_report.py %*
set "IZZI_CHECK_RESULT=%ERRORLEVEL%"
pause
exit /b %IZZI_CHECK_RESULT%
