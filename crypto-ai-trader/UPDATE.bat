@echo off
cd /d "%~dp0"
title Aiterra v1.0.0 - Update
color 0B

cls
echo.
echo  ============================================================
echo   Aiterra v1.0.0  --  Update (keeps your settings and data)
echo  ============================================================
echo.
echo   This updates the program code and dependencies.
echo   Your saved data is NOT touched:
echo     - config\settings.yml   (your API keys / tokens)
echo     - data\trades.db        (trade history)
echo     - models\signal_model.pkl (trained AI model)
echo.

REM --- Confirm we are in a real install -----------------------
if not exist requirements.txt (
    echo  ERROR: requirements.txt not found in this folder.
    echo  Make sure you extracted the new files into your existing
    echo  Aiterra folder (choose "Replace the files" when asked).
    echo.
    pause & exit /b 1
)

REM --- venv check ---------------------------------------------
if not exist venv\Scripts\activate.bat (
    echo  No virtual environment found. Running full install instead...
    echo.
    call INSTALL.bat
    exit /b 0
)

call venv\Scripts\activate.bat
if errorlevel 1 (
    echo  ERROR: Cannot activate venv. Try running INSTALL.bat.
    pause & exit /b 1
)

REM --- Preserve config: only create if missing ----------------
if not exist config\settings.yml (
    if exist config\settings.example.yml (
        copy config\settings.example.yml config\settings.yml >nul
        echo  Note: no existing settings.yml found - created a fresh one.
    )
) else (
    echo  [OK] Existing config\settings.yml preserved.
)
if not exist data   mkdir data
if not exist models mkdir models

REM --- Upgrade dependencies -----------------------------------
echo.
echo  Updating dependencies (may take a few minutes)...
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

echo.
echo  ============================================================
echo   Update complete!  Your API keys and history are intact.
echo.
echo   Double-click START.bat to launch the updated app.
echo  ============================================================
echo.
pause
