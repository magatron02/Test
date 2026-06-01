@echo off
title Aiterra - Stop
color 0C

echo.
echo  ============================================================
echo   Aiterra v1.0.0  --  Stopping...
echo  ============================================================
echo.

REM Kill by port 8888
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8888 " ^| findstr "LISTENING"') do (
    echo  Killing PID %%a on port 8888
    taskkill /PID %%a /F >nul 2>&1
)

REM Also try by window title
taskkill /FI "WINDOWTITLE eq Aiterra v1.0.0*" /F >nul 2>&1

echo  [OK] Aiterra stopped.
echo.
timeout /t 2 /nobreak >nul
