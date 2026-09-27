@echo off
title AI bottrade - 24/7 Launcher
cd /d %~dp0

if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found!
    echo Please double-click 'setup_windows.bat' first.
    pause
    exit /b 1
)

echo ========================================================
echo  AI bottrade - Launching 24/7 Services on Windows VPS
echo ========================================================
echo 1. Launching 24/7 Market Monitor (Telegram/Discord Alerts)...
start "AI bottrade - 24/7 Live Monitor" cmd /k "title AI Monitor & call .venv\Scripts\activate.bat & python main.py monitor --assets ""GOLD (XAU/USD)"" ""BTC/USDT"" ""SILVER (XAG/USD)"" --timeframe 1h --interval 60"

echo 2. Launching Streamlit Web Dashboard (Port 8501)...
start "AI bottrade - Web Dashboard" cmd /k "title AI Dashboard & call .venv\Scripts\activate.bat & streamlit run app.py --server.port 8501 --server.address 0.0.0.0"

echo ========================================================
echo  All services are running!
echo  - Web Dashboard: http://localhost:8501
echo  - You can minimize the two command prompt windows.
echo  - They will keep running 24/7 in the background.
echo ========================================================
timeout /t 5
