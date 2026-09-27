@echo off
title AI bottrade - 24/7 Launcher
cd /d %~dp0

if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment (.venv) not found!
    echo Please run "setup_windows.bat" first.
    echo.
    pause
    exit /b 1
)

echo ========================================================
echo  AI bottrade - Launching 24/7 Services on Windows VPS
echo ========================================================
echo 1. Launching 24/7 Multi-Timeframe Monitor (15m & 1h)...
start "AI bottrade - 24/7 Live Monitor" cmd /k "call .venv\Scripts\activate.bat && python main.py monitor --assets "GOLD (XAU/USD)" "BTC/USDT" "SILVER (XAG/USD)" --timeframes 15m 1h --interval 60"

echo 2. Launching Streamlit Web Dashboard (Port 8501)...
start "AI bottrade - Web Dashboard" cmd /k "call .venv\Scripts\activate.bat && streamlit run app.py --server.port 8501 --server.address 0.0.0.0"

echo.
echo ========================================================
echo  All services are running!
echo  - Web Dashboard: http://localhost:8501
echo  - Multi-Timeframe Scanning: 15m (Scalp) & 1h (Swing)
echo  - You can minimize both command prompt windows.
echo ========================================================
timeout /t 5
