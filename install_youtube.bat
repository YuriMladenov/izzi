@echo off
cd /d "%~dp0"
py -m pip install --upgrade "yt-dlp[default]"
if errorlevel 1 (
 echo Installation failed.
) else (
 echo yt-dlp installed. Install Deno or a recent Node.js runtime for YouTube extraction.
 echo Recommended Windows commands:
 echo winget install --id DenoLand.Deno -e
 echo winget install --id Gyan.FFmpeg -e
 echo Restart terminals after installing Deno and FFmpeg.
 echo Restart capture after installation.
)
pause
