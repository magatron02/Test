@echo off
cd /d "%~dp0"
title Aiterra v2.0.0 - Running
color 0A

cls
echo.
echo  ============================================================
echo   Aiterra v2.0.0  --  AI Crypto Trader
echo  ============================================================
echo.

if not exist venv\Scripts\activate.bat (
    echo  ERROR: Not installed yet!
    echo  Please double-click INSTALL.bat first.
    echo.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

echo  Starting Aiterra...
echo  Browser will open at http://localhost:8888
echo.
echo  Close this window to stop the program.
echo  ============================================================
echo.

REM Open browser after 4 seconds
start /b cmd /c "timeout /t 4 /nobreak >nul && start http://localhost:8888"

python -m src.main

if errorlevel 1 (
    echo.
    echo  ERROR: Aiterra crashed. See error above.
    pause
)
