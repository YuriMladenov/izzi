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
if not "%IZZI_UPDATE_BRANCH%"=="main" if not "%IZZI_UPDATE_BRANCH%"=="WebUI" (
    echo ERROR: Updates require main or WebUI. No changes were made.
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

echo Fetching main...
rem A remote-tracking ref is only updated with the "+" refspec. Without it Git
rem refuses with "non-fast-forward" whenever origin/main already points at a
rem different commit, for example after a manual fetch. --prune also removes
rem deleted branches without touching archive/ or state/.
git fetch --prune origin
if errorlevel 1 (
    echo ERROR: Could not fetch main. Read the Git message above.
    goto failed
)

git show-ref --verify --quiet refs/remotes/origin/main
if errorlevel 1 (
    echo ERROR: origin/main is missing after fetching. Check the origin URL.
    goto failed
)

git merge-base --is-ancestor HEAD refs/remotes/origin/main
if errorlevel 1 (
    echo ERROR: The current branch has commits that are not in origin/main.
    echo Update stopped. Your local commits were preserved.
    echo.
    echo The checkout is probably on an old side branch that was merged into main
    echo under a different name. Check what gets replaced before continuing:
    echo     git log --oneline -5
    echo     git log --oneline -5 refs/remotes/origin/main
    echo.
    echo To keep your work, move it aside first:
    echo     git branch backup-before-update
    echo To switch to the published code, run:
    echo     git reset --hard refs/remotes/origin/main
    echo Your archive and state folders are ignored by Git and are not touched.
    goto failed
)

git show-ref --verify --quiet refs/heads/main
if errorlevel 1 (
    git switch -c main --track origin/main
) else (
    git merge-base --is-ancestor refs/heads/main refs/remotes/origin/main
    if errorlevel 1 (
        echo ERROR: Local main has commits not included in origin/main.
        echo Update stopped. Your local commits were preserved.
        goto failed
    )
    git switch main
)
if errorlevel 1 (
    echo ERROR: Could not switch to main.
    goto failed
)

echo Updating main...
git merge --ff-only refs/remotes/origin/main
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
