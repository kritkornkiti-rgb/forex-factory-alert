@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ========================================================
echo   AI bottrade - Auto-Sync with GitHub ^& Launcher
echo ========================================================
echo [*] กำลังตรวจสอบและอัปเดตโค้ดล่าสุดจาก GitHub...
git pull
echo [*] อัปเดตเรียบร้อย กำลังเริ่มระบบ...
timeout /t 2 /nobreak >nul
start "AI bottrade - 24/7 Live Monitor" run_monitor_windows.bat
start "AI bottrade - Web Dashboard" run_dashboard_windows.bat
