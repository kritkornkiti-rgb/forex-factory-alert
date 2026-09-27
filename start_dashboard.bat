@echo off
title AI Web Dashboard
cd /d C:\AI bottrade
call .venv\Scripts\activate.bat
echo Starting Dashboard on http://localhost:8501 ...
python -m streamlit run app.py --server.port 8501 --server.address 0.0.0.0
pause
