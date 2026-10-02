@echo off
cd /d "%~dp0"
py tools\lesson_diagnostic.py %*
set "IZZI_REPORT_RESULT=%ERRORLEVEL%"
pause
exit /b %IZZI_REPORT_RESULT%
