@echo off
cd /d "%~dp0"
title Aiterra v1.0.24 - Update
color 0B

cls
echo.
echo  ============================================================
echo   Aiterra v1.0.24  --  Update
echo  ============================================================
echo.
echo   Upgrades the program and brings your data into this version.
echo   Nothing you entered before is deleted:
echo     - config\settings.yml      (your API keys / tokens)
echo     - data\trades.db           (trade history)
echo     - models\signal_model.pkl  (trained AI model)
echo.
echo   It imports them automatically from a previous Aiterra folder
echo   if you extracted this version next to the old one, and adds
echo   any new settings this version introduced (your values win).
echo.

REM --- Confirm we are in a real install -----------------------
if not exist requirements.txt (
    echo  ERROR: requirements.txt not found in this folder.
    echo  Extract ALL the new files into this folder first.
    echo.
    pause & exit /b 1
)

REM --- Python check -------------------------------------------
python --version >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Python not found. Install Python 3.10+ from python.org
    echo  (tick "Add Python to PATH"), then run UPDATE.bat again.
    pause & exit /b 1
)

REM --- venv: reuse if present, else create --------------------
if not exist venv\Scripts\activate.bat (
    echo  No virtual environment yet - creating one...
    python -m venv venv
    if errorlevel 1 (
        echo  ERROR: Failed to create virtual environment.
        pause & exit /b 1
    )
)

call venv\Scripts\activate.bat
if errorlevel 1 (
    echo  ERROR: Cannot activate venv. Try running INSTALL.bat.
    pause & exit /b 1
)

REM --- Upgrade dependencies (needed before migrate uses pyyaml) -
echo.
echo  [1/2] Updating dependencies (may take a few minutes)...
echo.
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt --upgrade
if errorlevel 1 (
    echo.
    echo  ERROR: Dependency update failed.
    echo    - Try running UPDATE.bat as Administrator
    echo    - Check your internet connection
    pause & exit /b 1
)

REM --- Import / merge user data -------------------------------
echo.
echo  [2/2] Importing your data and merging new settings...
echo.
if not exist data   mkdir data
if not exist models mkdir models
python migrate.py

echo.
echo  ============================================================
echo   Update complete!  Your API keys, history and model are intact.
echo.
echo   Double-click START.bat to launch the updated app.
echo  ============================================================
echo.
pause
