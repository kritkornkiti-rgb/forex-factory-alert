@echo off
cd /d "%~dp0"
echo ========================================================
echo  AI bottrade - Starting 24/7 Live Market Monitor...
echo ========================================================
call .venv\Scripts\activate.bat

:loop
echo [%time%] Starting Live Market Monitor...
python main.py monitor
echo.
echo [WARNING] Monitor stopped or disconnected. Auto-restarting in 5 seconds...
ping 127.0.0.1 -n 6 >nul
goto loop

