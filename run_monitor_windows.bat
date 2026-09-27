@echo off
cd /d "%~dp0"
echo ========================================================
echo  AI bottrade - Starting 24/7 Live Market Monitor...
echo ========================================================
call .venv\Scripts\activate.bat
python main.py monitor
pause
