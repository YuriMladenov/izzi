@echo off
cd /d "%~dp0.."
py checks\test_mp4_range.py %*
set "IZZI_CHECK_RESULT=%ERRORLEVEL%"
pause
exit /b %IZZI_CHECK_RESULT%
