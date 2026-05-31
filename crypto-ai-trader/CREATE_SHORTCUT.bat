@echo off
title Create Desktop Shortcut
echo Creating desktop shortcut for Aiterra v1.0.0...

set "TARGET=%~dp0START.bat"
set "SHORTCUT=%USERPROFILE%\Desktop\Aiterra v1.0.0.lnk"
set "ICON=%~dp0src\web\static\img\icon.ico"
set "WORKDIR=%~dp0"

powershell -Command "$WS = New-Object -ComObject WScript.Shell; $SC = $WS.CreateShortcut('%SHORTCUT%'); $SC.TargetPath = '%TARGET%'; $SC.WorkingDirectory = '%WORKDIR%'; $SC.WindowStyle = 1; $SC.Description = 'Aiterra v1.0.0'; $SC.Save()"

if exist "%SHORTCUT%" (
    echo.
    echo Shortcut created on Desktop: "Aiterra v1.0.0"
) else (
    echo Failed to create shortcut.
)
pause
