@echo off
cd /d "%~dp0"
echo Start start_library.bat first in another window.
py test_all_assembled.py
pause
