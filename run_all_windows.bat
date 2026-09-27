@echo off
cd /d "%~dp0"
start "AI bottrade - 24/7 Live Monitor" run_monitor_windows.bat
start "AI bottrade - Web Dashboard" run_dashboard_windows.bat
