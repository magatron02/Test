@echo off
title AI Auto Trader - Setup
color 0A
echo.
echo  ============================================
echo    AI Auto Trader - First Time Setup
echo  ============================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found!
    echo Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

echo [1/4] Creating virtual environment...
python -m venv venv
if errorlevel 1 ( echo [ERROR] Failed to create venv & pause & exit /b 1 )

echo [2/4] Activating venv...
call venv\Scripts\activate.bat

echo [3/4] Installing dependencies (this may take a few minutes)...
pip install --upgrade pip -q
pip install -r requirements.txt
if errorlevel 1 ( echo [ERROR] Failed to install dependencies & pause & exit /b 1 )

echo [4/4] Creating config file...
if not exist config\settings.yml (
    copy config\settings.example.yml config\settings.yml
    echo     config\settings.yml created
) else (
    echo     config\settings.yml already exists, skipping
)

if not exist data mkdir data
if not exist models mkdir models

echo.
echo  ============================================
echo    Setup Complete!
echo    Run START.bat to launch the app
echo  ============================================
echo.
pause
