@echo off
title AI bottrade - 24/7 Live Market Monitor
cd /d %~dp0

if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found! Please run "setup_windows.bat" first.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
python main.py monitor --assets "GOLD (XAU/USD)" "BTC/USDT" "SILVER (XAG/USD)" --timeframe 1h --interval 60
pause
