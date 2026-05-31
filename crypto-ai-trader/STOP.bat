@echo off
title AI Auto Trader - Stop
color 0C
echo.
echo  ============================================
echo    AI Auto Trader - Stopping...
echo  ============================================
echo.

REM Kill Python process running the trader on port 8888
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8888 " ^| findstr "LISTENING"') do (
    echo Stopping process PID: %%a
    taskkill /PID %%a /F >nul 2>&1
)

REM Also try killing by window title
taskkill /FI "WINDOWTITLE eq AI Auto Trader*" /F >nul 2>&1

echo Done. Trader has been stopped.
echo.
timeout /t 2 >nul
