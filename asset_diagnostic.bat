@echo off
cd /d "%~dp0"
py tools\asset_diagnostic.py %*
pause
