@echo off
title AI bottrade - 24/7 Live Market Monitor
cd /d "%~dp0"

echo ========================================================
echo  AI bottrade - Starting 24/7 Live Market Monitor...
echo ========================================================

if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment (.venv) not found in:
    echo %cd%
    echo Please double-click "setup_windows.bat" first.
    echo.
    pause
    exit /b 1
)

call ".venv\Scripts\activate.bat"
python main.py monitor
pause
