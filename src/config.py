"""
AI bottrade - Global Configuration
Configuration settings for Crypto pairs, Precious Metals, ML models, and Risk Management.
"""
from dataclasses import dataclass
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models_saved"

# Supported Assets
SUPPORTED_ASSETS = {
    # Precious Metals (Yahoo Finance tickers)
    "GOLD (XAU/USD)": {
        "symbol": "GC=F",
        "alt_symbol": "XAUUSD=X",
        "category": "metal",
        "name": "Gold",
        "source": "yfinance",
        "fee_rate": 0.0003, # Typical metal spread/fee approx 0.03%
    },
    "SILVER (XAG/USD)": {
        "symbol": "SI=F",
        "alt_symbol": "XAGUSD=X",
        "category": "metal",
        "name": "Silver",
        "source": "yfinance",
        "fee_rate": 0.0005,
    },
    "PLATINUM (XPT/USD)": {
        "symbol": "PL=F",
        "category": "metal",
        "name": "Platinum",
        "source": "yfinance",
        "fee_rate": 0.0005,
    },
    # Crypto Pairs (Binance / CCXT / yfinance)
    "BTC/USDT": {
        "symbol": "BTC/USDT",
        "yfinance_symbol": "BTC-USD",
        "category": "crypto",
        "name": "Bitcoin",
        "source": "ccxt",
        "fee_rate": 0.00075, # 0.075% standard taker fee
    },
    "ETH/USDT": {
        "symbol": "ETH/USDT",
        "yfinance_symbol": "ETH-USD",
        "category": "crypto",
        "name": "Ethereum",
        "source": "ccxt",
        "fee_rate": 0.00075,
    },
    "SOL/USDT": {
        "symbol": "SOL/USDT",
        "yfinance_symbol": "SOL-USD",
        "category": "crypto",
        "name": "Solana",
        "source": "ccxt",
        "fee_rate": 0.00075,
    },
    "BNB/USDT": {
        "symbol": "BNB/USDT",
        "yfinance_symbol": "BNB-USD",
        "category": "crypto",
        "name": "BNB",
        "source": "ccxt",
        "fee_rate": 0.00075,
    },
    "XRP/USDT": {
        "symbol": "XRP/USDT",
        "yfinance_symbol": "XRP-USD",
        "category": "crypto",
        "name": "Ripple",
        "source": "ccxt",
        "fee_rate": 0.00075,
    }
}

# Supported Timeframes
SUPPORTED_TIMEFRAMES = ["15m", "1h", "4h", "1d"]

@dataclass
class TradingConfig:
    initial_balance: float = 10000.0  # Virtual USD/USDT
    risk_per_trade: float = 0.02      # 2% risk of equity per trade
    max_open_positions: int = 3
    sl_atr_multiplier: float = 1.5    # Stop-Loss: 1.5 x ATR
    tp_atr_multiplier: float = 2.5    # Take-Profit: 2.5 x ATR (Reward:Risk ~ 1.67:1)
    slippage: float = 0.0002          # 0.02% slippage estimation
    confidence_threshold: float = 0.55 # Minimum AI probability to execute a trade
