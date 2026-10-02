@echo off
cd /d "%~dp0.."
py checks\local_replay_smoke_test.py %*
set "IZZI_CHECK_RESULT=%ERRORLEVEL%"
pause
exit /b %IZZI_CHECK_RESULT%
