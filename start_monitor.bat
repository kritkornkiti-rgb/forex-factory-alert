@echo off
title AI 24/7 Monitor
cd /d C:\AI bottrade
call .venv\Scripts\activate.bat
echo Starting 24/7 Monitor...
python main.py monitor
pause
