@echo off
title AI bottrade - Environment Setup
cd /d %~dp0

echo ========================================================
echo  AI bottrade - Setting up Python Environment (Windows)
echo ========================================================

:: Check for python or py launcher
set PYTHON_CMD=
python --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=python
    goto :PYTHON_FOUND
)

py --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=py
    goto :PYTHON_FOUND
)

echo.
echo [ERROR] Python is not recognized in command line!
echo Windows cannot find "python" or "py".
echo.
echo Solution:
echo 1. Re-run the Python installer.
echo 2. Click "Modify" or "Reinstall".
echo 3. Check the box "Add Python to PATH".
echo.
pause
exit /b 1

:PYTHON_FOUND
echo Found Python command: %PYTHON_CMD%
%PYTHON_CMD% --version

if exist ".venv\Scripts\activate.bat" goto :VENV_EXISTS

echo.
echo [1/3] Creating virtual environment (.venv)...
%PYTHON_CMD% -m venv .venv
if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment!
    pause
    exit /b 1
)

:VENV_EXISTS
echo.
echo [2/3] Activating virtual environment...
call .venv\Scripts\activate.bat

echo.
echo [3/3] Installing dependencies from requirements.txt...
python -m pip install --upgrade pip
pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo [ERROR] Encountered error while installing packages.
    pause
    exit /b 1
)

echo.
echo ========================================================
echo  [SUCCESS] Setup Completed Successfully!
echo  You can now run "run_all_windows.bat" to start the bot.
echo ========================================================
echo.
pause
