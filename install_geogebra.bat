@echo off
cd /d "%~dp0"
py install_geogebra.py %*
set "IZZI_GGB_RESULT=%ERRORLEVEL%"
pause
exit /b %IZZI_GGB_RESULT%
