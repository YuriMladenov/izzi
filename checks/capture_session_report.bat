@echo off
cd /d "%~dp0.."
py checks\capture_session_report.py %*
set "IZZI_CHECK_RESULT=%ERRORLEVEL%"
pause
exit /b %IZZI_CHECK_RESULT%
