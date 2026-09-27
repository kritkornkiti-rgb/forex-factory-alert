@echo off
title AI bottrade - Environment Setup
cd /d %~dp0
echo ========================================================
echo  AI bottrade - Setting up Python Environment (Windows)
echo ========================================================

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3.10, 3.11, or 3.12 from python.org
    echo Make sure to check "Add python.exe to PATH" during installation.
    pause
    exit /b 1
)

if not exist ".venv" (
    echo [1/3] Creating virtual environment (.venv)...
    python -m venv .venv
) else (
    echo [1/3] Virtual environment (.venv) already exists.
)

echo [2/3] Activating virtual environment...
call .venv\Scripts\activate.bat

echo [3/3] Installing dependencies from requirements.txt...
python -m pip install --upgrade pip
pip install -r requirements.txt

echo ========================================================
echo  [SUCCESS] Setup Completed!
echo  You can now run 'run_all_windows.bat' to start the bot.
echo ========================================================
pause
