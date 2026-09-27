@echo off
title AI bottrade - 24/7 Launcher
cd /d "%~dp0"

echo ========================================================
echo  AI bottrade - Launching 24/7 Services on Windows VPS
echo ========================================================

if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment (.venv) not found in:
    echo %cd%
    echo Please double-click "setup_windows.bat" first.
    echo.
    pause
    exit /b 1
)

echo [1/2] Starting 24/7 Live Market Monitor in persistent window...
start "AI bottrade - 24/7 Live Monitor" cmd /k "cd /d "%~dp0" && call run_monitor_windows.bat"

echo [2/2] Starting Streamlit Web Dashboard in persistent window...
start "AI bottrade - Web Dashboard" cmd /k "cd /d "%~dp0" && call run_dashboard_windows.bat"

echo.
echo ========================================================
echo  [SUCCESS] All services launched in persistent windows!
echo  - Web Dashboard: http://localhost:8501
echo  - Live Monitor: Active in separate window
echo ========================================================
pause
