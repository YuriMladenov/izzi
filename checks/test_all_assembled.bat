@echo off
cd /d "%~dp0.."
py checks\test_all_assembled.py %*
set "IZZI_CHECK_RESULT=%ERRORLEVEL%"
pause
exit /b %IZZI_CHECK_RESULT%
