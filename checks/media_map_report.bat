@echo off
cd /d "%~dp0.."
py checks\media_map_report.py %*
set "IZZI_CHECK_RESULT=%ERRORLEVEL%"
pause
exit /b %IZZI_CHECK_RESULT%
