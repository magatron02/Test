@echo off
title Aiterra — Build Standalone EXE
color 0B
chcp 65001 >nul 2>&1

cls
echo.
echo  ╔══════════════════════════════════════════════════╗
echo  ║   Aiterra — Build Standalone .exe (PyInstaller)  ║
echo  ╚══════════════════════════════════════════════════╝
echo.
echo  สร้างไฟล์ .exe ที่รันได้โดยไม่ต้องติดตั้ง Python
echo  ใช้เวลาประมาณ 3-5 นาที
echo.

if not exist venv\Scripts\activate.bat (
    echo  [ERROR] ยังไม่ได้ติดตั้ง — รัน INSTALL.bat ก่อน
    pause & exit /b 1
)

call venv\Scripts\activate.bat

REM ติดตั้ง PyInstaller ถ้ายังไม่มี
python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo  ติดตั้ง PyInstaller...
    pip install pyinstaller --quiet
)

echo  กำลัง build...
echo.
pyinstaller ai_trader.spec --noconfirm

if errorlevel 1 (
    echo.
    echo  [ERROR] Build ไม่สำเร็จ — ดูข้อผิดพลาดด้านบน
    pause & exit /b 1
)

echo.
echo  ╔══════════════════════════════════════════════════╗
echo  ║   ✅  Build สำเร็จ!                              ║
echo  ║                                                  ║
echo  ║   ไฟล์อยู่ที่:  dist\Aiterra\Aiterra.exe         ║
echo  ║                                                  ║
echo  ║   วิธีแจกจ่าย: zip โฟลเดอร์ dist\Aiterra\       ║
echo  ║   ผู้รับสามารถรัน Aiterra.exe ได้เลย             ║
echo  ║   โดยไม่ต้องติดตั้ง Python                       ║
echo  ╚══════════════════════════════════════════════════╝
echo.
pause
