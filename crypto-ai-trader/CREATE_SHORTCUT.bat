@echo off
title Create Desktop Shortcut
echo Creating desktop shortcut for AI Auto Trader...

set "TARGET=%~dp0START.bat"
set "SHORTCUT=%USERPROFILE%\Desktop\AI Auto Trader.lnk"
set "ICON=%~dp0src\web\static\img\icon.ico"
set "WORKDIR=%~dp0"

powershell -Command "$WS = New-Object -ComObject WScript.Shell; $SC = $WS.CreateShortcut('%SHORTCUT%'); $SC.TargetPath = '%TARGET%'; $SC.WorkingDirectory = '%WORKDIR%'; $SC.WindowStyle = 1; $SC.Description = 'AI Auto Trader'; $SC.Save()"

if exist "%SHORTCUT%" (
    echo.
    echo Shortcut created on Desktop: "AI Auto Trader"
) else (
    echo Failed to create shortcut.
)
pause
