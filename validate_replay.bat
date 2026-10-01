@echo off
cd /d "%~dp0"
py tools\validate_replay.py
set "IZZI_TEST_RESULT=%ERRORLEVEL%"
pause
exit /b %IZZI_TEST_RESULT%
