@echo off
cd /d "%~dp0.."
py checks\book_readiness_report.py %*
set "IZZI_CHECK_RESULT=%ERRORLEVEL%"
pause
exit /b %IZZI_CHECK_RESULT%
