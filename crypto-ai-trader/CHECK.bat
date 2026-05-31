@echo off
title AI Auto Trader - System Check
color 0B
echo.
echo  ============================================
echo    AI Auto Trader - System Check
echo  ============================================
echo.

REM ── Python ──────────────────────────────────
echo [1/5] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo   [FAIL] Python not found!
    echo   Install from https://python.org ^(3.10+^) and check "Add to PATH"
    goto :fail
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo   [OK] %%v

REM ── Virtual env ─────────────────────────────
echo [2/5] Checking virtual environment...
if exist venv\Scripts\activate.bat (
    echo   [OK] venv exists
) else (
    echo   [WARN] venv not found — run SETUP.bat first
)

REM ── Config file ─────────────────────────────
echo [3/5] Checking config...
if exist config\settings.yml (
    echo   [OK] config\settings.yml exists
) else if exist config\settings.example.yml (
    echo   [WARN] settings.yml missing — will be created from example on first run
) else (
    echo   [FAIL] config\settings.example.yml missing!
    goto :fail
)

REM ── Port 8888 ───────────────────────────────
echo [4/5] Checking port 8888...
netstat -aon 2>nul | findstr ":8888 " | findstr "LISTENING" >nul
if errorlevel 1 (
    echo   [OK] Port 8888 is free
) else (
    echo   [WARN] Port 8888 is already in use — another instance may be running
    echo          Run STOP.bat first, or change port in config\settings.yml
)

REM ── Quick import test ────────────────────────
echo [5/5] Testing Python imports...
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat >nul 2>&1
    python -c "import fastapi, uvicorn, sqlalchemy, ccxt, numpy, pandas, sklearn; print('   [OK] All core packages installed')" 2>nul
    if errorlevel 1 (
        echo   [WARN] Some packages missing — run SETUP.bat to reinstall
    )
) else (
    echo   [SKIP] venv not found
)

echo.
echo  ============================================
echo    Check complete! Run START.bat to launch.
echo  ============================================
echo.
goto :end

:fail
echo.
echo  [FAILED] Fix the issues above then try again.
echo.

:end
pause
