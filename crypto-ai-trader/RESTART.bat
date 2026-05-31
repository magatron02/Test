@echo off
title AI Auto Trader - Restart
color 0E
echo.
echo  ============================================
echo    AI Auto Trader - Restarting...
echo  ============================================
echo.

REM Stop first
call STOP.bat

REM Wait a moment
timeout /t 3 >nul

REM Start again
call START.bat
