@echo off
setlocal
cd /d "%~dp0"

where git >nul 2>nul
if errorlevel 1 (
    echo ERROR: Git is not installed or is not in PATH.
    goto failed
)

git rev-parse --is-inside-work-tree >nul 2>nul
if errorlevel 1 (
    echo ERROR: This folder is not a Git checkout. Download it with git clone first.
    goto failed
)

set "IZZI_UPDATE_BRANCH="
for /f "delims=" %%B in ('git branch --show-current') do set "IZZI_UPDATE_BRANCH=%%B"
if not "%IZZI_UPDATE_BRANCH%"=="main" (
    echo ERROR: Updates require the main branch. No changes were made.
    goto failed
)

git status --porcelain >nul 2>nul
if errorlevel 1 (
    echo ERROR: Could not check local changes.
    goto failed
)
set "IZZI_UPDATE_DIRTY="
for /f "delims=" %%L in ('git status --porcelain') do set "IZZI_UPDATE_DIRTY=1"
if defined IZZI_UPDATE_DIRTY (
    echo ERROR: Local changes or untracked files exist. Update stopped.
    git status --short
    echo Keep your changes and resolve them before updating.
    goto failed
)

echo Stop the replay server and capture proxy before updating.
echo The update uses fast-forward only. It does not reset or clean your files.
pause

git pull --ff-only origin main
if errorlevel 1 (
    echo ERROR: Update failed. Read the Git message above.
    goto failed
)

echo.
echo Update complete. Start start_library.bat again.
git log -1 --oneline
pause
exit /b 0

:failed
echo.
pause
exit /b 1
