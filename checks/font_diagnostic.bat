@echo off
cd /d "%~dp0.."
py checks\font_diagnostic.py %*
set "IZZI_CHECK_RESULT=%ERRORLEVEL%"
pause
exit /b %IZZI_CHECK_RESULT%
