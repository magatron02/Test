@echo off
title AI Auto Trader
color 0A

REM Check if venv exists
if not exist venv\Scripts\activate.bat (
    echo [ERROR] Virtual environment not found!
    echo Please run SETUP.bat first.
    pause
    exit /b 1
)

echo.
echo  ============================================
echo    AI Auto Trader - Starting...
echo  ============================================
echo.

call venv\Scripts\activate.bat
python -m src.main

REM If crash, pause to show error
if errorlevel 1 (
    echo.
    echo [ERROR] Application crashed. See error above.
    pause
)
