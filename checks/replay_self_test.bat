@echo off
cd /d "%~dp0.."
py checks\replay_self_test.py %*
set "IZZI_CHECK_RESULT=%ERRORLEVEL%"
pause
exit /b %IZZI_CHECK_RESULT%
