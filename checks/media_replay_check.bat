@echo off
cd /d "%~dp0.."
py checks\media_replay_check.py %*
set "IZZI_CHECK_RESULT=%ERRORLEVEL%"
pause
exit /b %IZZI_CHECK_RESULT%
