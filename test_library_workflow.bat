@echo off
cd /d "%~dp0"
py tools\test_library_workflow.py
set "IZZI_TEST_RESULT=%ERRORLEVEL%"
pause
exit /b %IZZI_TEST_RESULT%
