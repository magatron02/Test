@echo off
cd /d "%~dp0"
setlocal enabledelayedexpansion
title Aiterra v1.0.24 - Install
color 0A

cls
echo.
echo  ============================================================
echo   Aiterra v1.0.24  --  AI Crypto Trader
echo   First Time Setup / Install
echo  ============================================================
echo.

REM --- 1. Check Python ----------------------------------------
echo  [1/5] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  ERROR: Python not found on this computer.
    echo.
    echo  Please install Python 3.10 or newer from:
    echo    https://www.python.org/downloads/
    echo.
    echo  IMPORTANT: Check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo    Found Python %PYVER%

for /f "tokens=1,2 delims=." %%a in ("%PYVER%") do (
    set PY_MAJOR=%%a
    set PY_MINOR=%%b
)
if %PY_MAJOR% LSS 3 (
    echo  ERROR: Python 3.10+ required. Found %PYVER%
    pause & exit /b 1
)
if %PY_MAJOR% EQU 3 if %PY_MINOR% LSS 10 (
    echo  ERROR: Python 3.10+ required. Found %PYVER%
    pause & exit /b 1
)
echo    [OK] Version check passed

REM --- 2. Virtual environment ---------------------------------
echo.
echo  [2/5] Creating virtual environment...
if exist venv\Scripts\activate.bat (
    echo    [OK] venv already exists, skipping
) else (
    python -m venv venv
    if errorlevel 1 (
        echo  ERROR: Failed to create virtual environment
        pause & exit /b 1
    )
    echo    [OK] venv created
)

REM --- 3. Activate --------------------------------------------
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo  ERROR: Cannot activate venv
    pause & exit /b 1
)

REM --- 4. Upgrade pip + install packages ---------------------
echo.
echo  [3/5] Upgrading pip...
python -m pip install --upgrade pip --quiet
echo    [OK]

echo.
echo  [4/5] Installing packages (may take 3-7 minutes)...
echo    Please do not close this window.
echo.
pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo  ERROR: Package installation failed.
    echo.
    echo  Possible fixes:
    echo    - Run INSTALL.bat as Administrator
    echo    - Check internet connection
    echo    - Temporarily disable antivirus
    echo.
    pause & exit /b 1
)
echo.
echo    [OK] All packages installed

REM --- 5. Config + folders ------------------------------------
echo.
echo  [5/5] Setting up config and importing any previous data...
if not exist data   mkdir data
if not exist models mkdir models

REM migrate.py auto-imports settings / history / model from an older
REM Aiterra folder if one exists nearby, otherwise creates a fresh config.
python migrate.py
if errorlevel 1 (
    REM Never block install on migration — fall back to a plain fresh config.
    if not exist config\settings.yml (
        copy config\settings.example.yml config\settings.yml >nul
    )
)

REM --- Done ---------------------------------------------------
echo.
echo  ============================================================
echo   Installation complete!
echo  ============================================================
echo.
echo   Next steps:
echo.
echo   1. (Optional) Edit config\settings.yml to add:
echo        - Exchange API keys (Binance / Bitkub / OKX)
echo        - Claude API key  (for AI analysis)
echo        - LINE / Telegram token  (for alerts)
echo      Skip this step to run in Demo mode (no real money).
echo.
echo   2. Double-click START.bat to launch Aiterra.
echo      Your browser will open http://localhost:8888
echo.
echo   Exchange API key pages:
echo     Binance    : binance.com/en/my/settings/api
echo     Binance TH : binance.th/en/profile/api
echo     Bitkub     : bitkub.com/sitesetting/api
echo     OKX        : okx.com/account/my-api
echo.
echo  ============================================================
echo.

set /p STARTAPP=  Start Aiterra now? [Y/N] :
if /i "!STARTAPP!"=="Y" (
    echo.
    echo  Starting Aiterra...
    start "" cmd /k "title Aiterra v1.0.24 && call venv\Scripts\activate.bat && python -m src.main"
    timeout /t 4 /nobreak >nul
    start "" "http://localhost:8888"
) else (
    echo.
    echo  You can start anytime by double-clicking START.bat
)

echo.
pause
endlocal
