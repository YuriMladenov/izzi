@echo off
cd /d "%~dp0.."
py checks\test_library_workflow.py %*
set "IZZI_CHECK_RESULT=%ERRORLEVEL%"
pause
exit /b %IZZI_CHECK_RESULT%
