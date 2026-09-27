@echo off
cd /d "%~dp0"
echo ========================================================
echo  AI bottrade - Starting Web Dashboard...
echo ========================================================
call .venv\Scripts\activate.bat
streamlit run app.py --server.port 8501 --server.address 0.0.0.0
pause
