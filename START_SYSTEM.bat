@echo off
title Dual Market Trading Engine
cd /d "C:\Users\thush\trading_system"

:: Launch Streamlit web backplane minimized
start "TradingDashboard" /min "C:\Users\thush\trading_system\.venv\Scripts\python.exe" -m streamlit run dashboard.py --server.port 8501 --server.headless true

:: Launch Master Trading Bot & Headless Engine
"C:\Users\thush\trading_system\.venv\Scripts\python.exe" main.py
pause