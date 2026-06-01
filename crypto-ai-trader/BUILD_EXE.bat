@echo off
cd /d "%~dp0"
title Aiterra - Build Standalone EXE
color 0B

cls
echo.
echo  ============================================================
echo   Aiterra v1.0.0  --  Build Standalone .exe (PyInstaller)
echo   Creates a single folder you can share without Python.
echo   Build time: ~3-5 minutes
echo  ============================================================
echo.

if not exist venv\Scripts\activate.bat (
    echo  ERROR: Not installed yet. Run INSTALL.bat first.
    pause & exit /b 1
)

call venv\Scripts\activate.bat

REM Install PyInstaller if missing
python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo  Installing PyInstaller...
    pip install pyinstaller --quiet
)

echo  Building...
echo.
pyinstaller ai_trader.spec --noconfirm

if errorlevel 1 (
    echo.
    echo  ERROR: Build failed. See error above.
    pause & exit /b 1
)

echo.
echo  ============================================================
echo   Build complete!
echo.
echo   Output: dist\Aiterra\Aiterra.exe
echo.
echo   To distribute: zip the entire dist\Aiterra\ folder.
echo   Recipients can run Aiterra.exe directly without Python.
echo  ============================================================
echo.
pause
