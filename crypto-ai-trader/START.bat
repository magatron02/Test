@echo off
title Aiterra v1.0.0 — กำลังทำงาน
color 0A
chcp 65001 >nul 2>&1

cls
echo.
echo  ╔══════════════════════════════════════════════════╗
echo  ║          Aiterra v1.0.0  — AI Crypto Trader      ║
echo  ╚══════════════════════════════════════════════════╝
echo.

if not exist venv\Scripts\activate.bat (
    echo  [ERROR] ยังไม่ได้ติดตั้ง!
    echo  กรุณาดับเบิลคลิก  INSTALL.bat  ก่อน
    echo.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

echo  กำลังเริ่มต้น...
echo  เปิดเบราว์เซอร์ที่  http://localhost:8888
echo.
echo  ปิดหน้าต่างนี้เพื่อหยุดโปรแกรม
echo  ─────────────────────────────────────────────────

REM เปิดเบราว์เซอร์หลังจาก 3 วินาที
start /b cmd /c "timeout /t 3 /nobreak >nul && start http://localhost:8888"

python -m src.main

if errorlevel 1 (
    echo.
    echo  [ERROR] โปรแกรมปิดตัวผิดปกติ
    echo  ดูข้อผิดพลาดด้านบน
    pause
)
