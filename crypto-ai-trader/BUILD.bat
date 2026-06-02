@echo off
title Aiterra v1.0.24 - Build Executable
color 0B
echo.
echo  ============================================
echo    Aiterra v1.0.24 - Building .exe
echo  ============================================
echo.

REM ── Check Python ────────────────────────────
python --version >nul 2>&1
if errorlevel 1 ( echo [ERROR] Python not found & pause & exit /b 1 )

REM ── Activate venv ───────────────────────────
if not exist venv\Scripts\activate.bat (
    echo [ERROR] venv not found — run SETUP.bat first
    pause & exit /b 1
)
call venv\Scripts\activate.bat

REM ── Install PyInstaller if missing ──────────
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [+] Installing PyInstaller...
    pip install pyinstaller -q
)

REM ── Build ───────────────────────────────────
echo [+] Building executable (this takes 2-5 minutes)...
pyinstaller ai_trader.spec --noconfirm --clean

if errorlevel 1 (
    echo [ERROR] Build failed!
    pause & exit /b 1
)

echo.
echo  ============================================
echo    Build Complete!
echo    Output folder: dist\Aiterra\
echo    Run: dist\Aiterra\Aiterra.exe
echo  ============================================
echo.
pause
