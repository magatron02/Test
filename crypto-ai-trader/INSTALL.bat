@echo off
setlocal enabledelayedexpansion
title Aiterra v1.0.0 — Installer
color 0A
chcp 65001 >nul 2>&1

cls
echo.
echo  ╔══════════════════════════════════════════════════╗
echo  ║          Aiterra v1.0.0  — AI Crypto Trader      ║
echo  ║          by Magatron02  /  ติดตั้งครั้งแรก       ║
echo  ╚══════════════════════════════════════════════════╝
echo.

REM ══════════════════════════════════════════════════════
REM  1. ตรวจ Python
REM ══════════════════════════════════════════════════════
echo  [1/5] ตรวจสอบ Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  ╔══════════════════════════════════════════════════╗
    echo  ║  [ERROR]  ไม่พบ Python บนเครื่อง                 ║
    echo  ║                                                  ║
    echo  ║  กรุณาติดตั้ง Python 3.10 หรือใหม่กว่า จาก:     ║
    echo  ║  https://www.python.org/downloads/              ║
    echo  ║                                                  ║
    echo  ║  สำคัญ: ติ๊ก "Add Python to PATH"               ║
    echo  ║         ก่อนกดติดตั้ง                            ║
    echo  ╚══════════════════════════════════════════════════╝
    echo.
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo       พบ Python %PYVER%

REM ตรวจเวอร์ชัน >= 3.10
for /f "tokens=1,2 delims=." %%a in ("%PYVER%") do (
    set PY_MAJOR=%%a
    set PY_MINOR=%%b
)
if %PY_MAJOR% LSS 3 (
    echo  [ERROR] ต้องการ Python 3.10+  ^(พบ %PYVER%^)
    pause & exit /b 1
)
if %PY_MAJOR% EQU 3 if %PY_MINOR% LSS 10 (
    echo  [ERROR] ต้องการ Python 3.10+  ^(พบ %PYVER%^)
    pause & exit /b 1
)
echo       [OK] เวอร์ชันผ่าน

REM ══════════════════════════════════════════════════════
REM  2. Virtual environment
REM ══════════════════════════════════════════════════════
echo.
echo  [2/5] สร้าง Virtual Environment...
if exist venv\Scripts\activate.bat (
    echo       [OK] venv มีอยู่แล้ว ข้ามขั้นตอนนี้
) else (
    python -m venv venv
    if errorlevel 1 (
        echo  [ERROR] สร้าง venv ไม่สำเร็จ
        pause & exit /b 1
    )
    echo       [OK] สร้าง venv สำเร็จ
)

REM ══════════════════════════════════════════════════════
REM  3. Activate + อัปเกรด pip
REM ══════════════════════════════════════════════════════
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo  [ERROR] เปิด venv ไม่ได้
    pause & exit /b 1
)
echo.
echo  [3/5] อัปเกรด pip...
python -m pip install --upgrade pip --quiet
echo       [OK]

REM ══════════════════════════════════════════════════════
REM  4. ติดตั้ง dependencies
REM ══════════════════════════════════════════════════════
echo.
echo  [4/5] ติดตั้ง packages  ^(อาจใช้เวลา 3-7 นาที^)...
echo       กรุณาอย่าปิดหน้าต่างนี้
echo.
pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo  ╔════════════════════════════════════════════════════╗
    echo  ║  [ERROR]  ติดตั้ง packages ไม่สำเร็จ              ║
    echo  ║                                                    ║
    echo  ║  วิธีแก้:                                          ║
    echo  ║  - รัน INSTALL.bat ในฐานะ Administrator           ║
    echo  ║  - ตรวจสอบการเชื่อมต่ออินเทอร์เน็ต               ║
    echo  ║  - ตรวจสอบ antivirus ไม่ block pip               ║
    echo  ╚════════════════════════════════════════════════════╝
    pause & exit /b 1
)
echo.
echo       [OK] ติดตั้ง packages ครบทุกตัว

REM ══════════════════════════════════════════════════════
REM  5. Config + โฟลเดอร์
REM ══════════════════════════════════════════════════════
echo.
echo  [5/5] ตั้งค่าเริ่มต้น...
if not exist data   mkdir data
if not exist models mkdir models

if not exist config\settings.yml (
    copy config\settings.example.yml config\settings.yml >nul
    echo       [OK] สร้าง config\settings.yml แล้ว
) else (
    echo       [OK] config\settings.yml มีอยู่แล้ว
)

REM ══════════════════════════════════════════════════════
REM  เสร็จแล้ว!
REM ══════════════════════════════════════════════════════
echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║   ✅  ติดตั้งเสร็จแล้ว!                              ║
echo  ╠══════════════════════════════════════════════════════╣
echo  ║                                                      ║
echo  ║   ขั้นตอนต่อไป (ทำแค่ครั้งเดียว):                   ║
echo  ║                                                      ║
echo  ║   1. เปิดไฟล์  config\settings.yml                  ║
echo  ║      ใส่ API key ของ exchange ที่ใช้                 ║
echo  ║      (ถ้าจะเทรดจริง — Demo ใช้ได้เลยโดยไม่ต้องใส่)  ║
echo  ║                                                      ║
echo  ║   2. ดับเบิลคลิก  START.bat  เพื่อเริ่มใช้งาน       ║
echo  ║      เบราว์เซอร์จะเปิด http://localhost:8888         ║
echo  ║                                                      ║
echo  ╠══════════════════════════════════════════════════════╣
echo  ║   Exchange API Keys (ไม่บังคับ — Demo ไม่ต้องใส่):  ║
echo  ║   • Binance    : binance.com/en/my/settings/api      ║
echo  ║   • Binance TH : www.binance.th/en/profile/api       ║
echo  ║   • Bitkub     : www.bitkub.com/sitesetting/api      ║
echo  ║   • OKX        : www.okx.com/account/my-api          ║
echo  ║                                                      ║
echo  ║   Claude AI Key (ไม่บังคับ — ใช้ hybrid โดยไม่มีก็ได้):║
echo  ║   • console.anthropic.com                            ║
echo  ╚══════════════════════════════════════════════════════╝
echo.

set /p STARTAPP="  เริ่มใช้งาน Aiterra เลยไหม? [Y/N] : "
if /i "!STARTAPP!"=="Y" (
    echo.
    echo  กำลังเปิด Aiterra...
    start "" cmd /k "call venv\Scripts\activate.bat && python -m src.main"
    timeout /t 3 /nobreak >nul
    start "" "http://localhost:8888"
) else (
    echo.
    echo  เปิดใช้งานได้ตลอดเวลาโดยดับเบิลคลิก START.bat
)

echo.
pause
endlocal
