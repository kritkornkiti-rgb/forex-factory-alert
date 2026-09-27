#!/bin/bash
set -e

# Make sure data and model directories exist
mkdir -p data models_saved

MODE=${1:-"all"}

if [ "$MODE" = "streamlit" ]; then
    echo "[AI bottrade] Starting Streamlit Web Dashboard on port 8501..."
    exec streamlit run app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true

elif [ "$MODE" = "monitor" ]; then
    echo "[AI bottrade] Starting 24/7 Live Market Monitor & Alerts..."
    exec python main.py monitor --assets "GOLD (XAU/USD)" "BTC/USDT" "SILVER (XAG/USD)" "ETH/USDT" --timeframe 1h --interval 60

elif [ "$MODE" = "all" ]; then
    echo "[AI bottrade] Launching 24/7 Monitor in background..."
    python main.py monitor --assets "GOLD (XAU/USD)" "BTC/USDT" "SILVER (XAG/USD)" "ETH/USDT" --timeframe 1h --interval 60 &
    MONITOR_PID=$!

    echo "[AI bottrade] Launching Streamlit Web Dashboard on port 8501..."
    streamlit run app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true &
    STREAMLIT_PID=$!

    trap "kill $MONITOR_PID $STREAMLIT_PID; exit 0" SIGINT SIGTERM

    wait
else
    # Allow running any custom command e.g. python main.py backtest
    exec "$@"
fi
