@echo off
cd /d "%~dp0"
py migrate_archive.py %*
if errorlevel 1 echo Migration failed. Read the error above.
pause
