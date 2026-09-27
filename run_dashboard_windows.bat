@echo off
title AI bottrade - Web Dashboard
cd /d "%~dp0"

echo ========================================================
echo  AI bottrade - Starting Web Dashboard...
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
echo Starting Streamlit on http://localhost:8501 ...
python -m streamlit run app.py --server.port 8501 --server.address 0.0.0.0
pause
