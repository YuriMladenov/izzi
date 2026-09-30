@echo off
cd /d "%~dp0"
py build_recovery_manifest.py
echo.
echo Now click your bookmark made from cache_bust_recovery_bookmarklet.txt
pause
