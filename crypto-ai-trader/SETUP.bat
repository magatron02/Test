@echo off
title AI Auto Trader - Setup
color 0A
echo.
echo  ============================================
echo    AI Auto Trader - First Time Setup
echo  ============================================
echo.

REM ── Python check ────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found!
    echo.
    echo  Please install Python 3.10+ from https://python.org
    echo  IMPORTANT: Check "Add Python to PATH" during installation
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo [OK] %%v found

REM ── Virtual environment ─────────────────────
echo.
echo [1/4] Creating virtual environment...
if exist venv (
    echo   venv already exists, skipping creation
) else (
    python -m venv venv
    if errorlevel 1 ( echo [ERROR] Failed to create venv & pause & exit /b 1 )
    echo   [OK] venv created
)

REM ── Activate ────────────────────────────────
echo [2/4] Activating venv...
call venv\Scripts\activate.bat
if errorlevel 1 ( echo [ERROR] Cannot activate venv & pause & exit /b 1 )

REM ── Dependencies ────────────────────────────
echo [3/4] Installing dependencies...
echo   This may take 3-5 minutes on first run...
pip install --upgrade pip -q
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install some packages
    echo   Try running as Administrator or check internet connection
    pause
    exit /b 1
)
echo   [OK] All packages installed

REM ── Config ──────────────────────────────────
echo [4/4] Setting up config...
if not exist config\settings.yml (
    copy config\settings.example.yml config\settings.yml >nul
    echo   [OK] config\settings.yml created
    echo.
    echo  ─────────────────────────────────────────
    echo   OPTIONAL: Edit config\settings.yml to add:
    echo   - Exchange API keys (Binance / OKX / Bitkub)
    echo   - Claude API key (for AI analysis)
    echo   - LINE / Telegram tokens (for alerts)
    echo.
    echo   For TESTNET (no real money):
    echo   - Binance: register at testnet.binance.vision
    echo   - Set testnet: true under exchanges.binance
    echo  ─────────────────────────────────────────
) else (
    echo   [OK] config\settings.yml already exists
)

if not exist data   mkdir data
if not exist models mkdir models

echo.
echo  ============================================
echo    Setup Complete!
echo.
echo    To start   : double-click START.bat
echo    To check   : double-click CHECK.bat
echo    To stop    : double-click STOP.bat
echo  ============================================
echo.
pause
