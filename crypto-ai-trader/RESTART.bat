@echo off
cd /d "%~dp0"
title Aiterra - Restart
color 0E

echo.
echo  ============================================================
echo   Aiterra v1.2.0  --  Restarting...
echo  ============================================================
echo.

call STOP.bat
timeout /t 3 /nobreak >nul
call START.bat
