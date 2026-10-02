@echo off
cd /d "%~dp0"
py checks\run_all.py %*
set "IZZI_CHECK_RESULT=%ERRORLEVEL%"
echo.
echo Checks finished. See SUMMARY above.
pause
exit /b %IZZI_CHECK_RESULT%
