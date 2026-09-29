@echo off
chcp 65001 >nul
title Forex Factory Red & Orange Folder News Tracker
cls

echo =====================================================================
echo 🔴 Forex Factory Red & Orange Folder News Tracker & Telegram Alert
echo    ตารางและระบบแจ้งเตือนข่าวกล่องแดง & กล่องส้ม (เวลาไทย UTC+7)
echo =====================================================================
echo.
echo กรุณาเลือกเมนูการใช้งาน:
echo   1) 🌐 เปิด Web Dashboard บนเบราว์เซอร์ (เวลานับถอยหลัง & เสียงเตือน)
echo   2) 📊 ดูตารางข่าวกล่องแดงและกล่องส้มใน Terminal ตอนนี้
echo   3) 📅 ดูเฉพาะข่าววันนี้ (Today Only)
echo   4) 📋 ดูข้อความสรุปข่าว (พร้อมคัดลอกลง LINE / Telegram)
echo   5) 🤖 ตั้งค่าเชื่อมต่อ Telegram Bot (ใส่ Token & Chat ID)
echo   6) 📲 ส่งสรุปข่าววันนี้เข้า Telegram ทันที
echo   7) 🚨 เปิดระบบเฝ้าระวังแจ้งเตือนอัตโนมัติ 24 ชม. (Telegram + Desktop)
echo   8) 🔔 ทดสอบส่งข้อความเข้า Telegram
echo   0) ❌ ออกจากการทำงาน
echo.

set /p choice="กดเลือกหมายเลข [1-8 หรือ 0] (ค่าเริ่มต้น: 1): "
if "%choice%"=="" set choice=1

set PYTHON_CMD=python
if exist .venv\Scripts\python.exe set PYTHON_CMD=.venv\Scripts\python.exe

if "%choice%"=="1" (
    echo.
    echo 🚀 กำลังเปิด Web Dashboard...
    %PYTHON_CMD% forex_news.py --web
) else if "%choice%"=="2" (
    echo.
    %PYTHON_CMD% forex_news.py --table
    echo.
    pause
) else if "%choice%"=="3" (
    echo.
    %PYTHON_CMD% forex_news.py --table --today
    echo.
    pause
) else if "%choice%"=="4" (
    echo.
    %PYTHON_CMD% forex_news.py --summary --today
    echo.
    pause
) else if "%choice%"=="5" (
    echo.
    %PYTHON_CMD% forex_news.py --setup-telegram
    echo.
    pause
) else if "%choice%"=="6" (
    echo.
    %PYTHON_CMD% forex_news.py --send-telegram-summary --today
    echo.
    pause
) else if "%choice%"=="7" (
    echo.
    %PYTHON_CMD% forex_news.py --monitor
) else if "%choice%"=="8" (
    echo.
    %PYTHON_CMD% forex_news.py --test-telegram
    echo.
    pause
) else if "%choice%"=="0" (
    exit /b 0
) else (
    %PYTHON_CMD% forex_news.py --web
)
