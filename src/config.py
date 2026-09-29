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
    # Forex Pairs (Yahoo Finance tickers)
    "EUR/USD": {
        "symbol": "EURUSD=X",
        "category": "forex",
        "name": "Euro / US Dollar",
        "source": "yfinance",
        "fee_rate": 0.0001,
    },
    "GBP/USD": {
        "symbol": "GBPUSD=X",
        "category": "forex",
        "name": "British Pound / US Dollar",
        "source": "yfinance",
        "fee_rate": 0.00015,
    },
    "USD/JPY": {
        "symbol": "USDJPY=X",
        "alt_symbol": "JPY=X",
        "category": "forex",
        "name": "US Dollar / Japanese Yen",
        "source": "yfinance",
        "fee_rate": 0.00015,
    },
    "AUD/USD": {
        "symbol": "AUDUSD=X",
        "category": "forex",
        "name": "Australian Dollar / US Dollar",
        "source": "yfinance",
        "fee_rate": 0.00015,
    },
    "USD/CAD": {
        "symbol": "USDCAD=X",
        "alt_symbol": "CAD=X",
        "category": "forex",
        "name": "US Dollar / Canadian Dollar",
        "source": "yfinance",
        "fee_rate": 0.00015,
    },
    "USD/CHF": {
        "symbol": "USDCHF=X",
        "alt_symbol": "CHF=X",
        "category": "forex",
        "name": "US Dollar / Swiss Franc",
        "source": "yfinance",
        "fee_rate": 0.00015,
    },
    "GBP/JPY": {
        "symbol": "GBPJPY=X",
        "category": "forex",
        "name": "British Pound / Japanese Yen",
        "source": "yfinance",
        "fee_rate": 0.0002,
    },
    "EUR/JPY": {
        "symbol": "EURJPY=X",
        "category": "forex",
        "name": "Euro / Japanese Yen",
        "source": "yfinance",
        "fee_rate": 0.0002,
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
SUPPORTED_TIMEFRAMES = ["5m", "15m", "1h", "4h", "1d"]

@dataclass
class TradingConfig:
    initial_balance: float = 10000.0  # Virtual USD/USDT
    risk_per_trade: float = 0.02      # 2% risk of equity per trade
    max_open_positions: int = 3
    sl_atr_multiplier: float = 1.5    # Stop-Loss: 1.5 x ATR
    tp_atr_multiplier: float = 2.5    # Take-Profit: 2.5 x ATR (Reward:Risk ~ 1.67:1)
    slippage: float = 0.0002          # 0.02% slippage estimation
    confidence_threshold: float = 0.45 # Minimum AI probability to execute a trade


def format_price(asset: str, price: float) -> str:
    """
    Formats price according to market standards:
    - JPY pairs (USD/JPY, GBP/JPY, EUR/JPY): 3 decimal places
    - All other Forex pairs (EUR/USD, GBP/USD, etc.): 5 decimal places
    - Metals: Gold (2 decimals), Silver (3 decimals)
    - Crypto: Standard (2 decimals), XRP (4 decimals)
    """
    asset_upper = asset.upper()

    # 1. JPY currency pairs -> exactly 3 decimal places
    if "JPY" in asset_upper:
        return f"{price:,.3f}"

    # 2. All other Forex currency pairs -> exactly 5 decimal places
    is_forex = False
    if any(fx in asset_upper for fx in ["EUR", "GBP", "AUD", "CAD", "CHF", "NZD", "=X"]) or ("USD" in asset_upper and "/" in asset_upper):
        if not any(m in asset_upper for m in ["GOLD", "SILVER", "PLATINUM", "XAU", "XAG", "XPT", "USDT"]):
            is_forex = True

    if is_forex:
        return f"{price:.5f}"

    # 3. Special commodities / crypto
    if "XRP" in asset_upper:
        return f"{price:.4f}"
    if "SILVER" in asset_upper or "XAG" in asset_upper:
        return f"{price:.3f}"

    return f"{price:,.2f}"


def format_currency_price(asset: str, price: float) -> str:
    """
    Adds $ for commodities and crypto, while keeping clean 5-digit/3-digit quote numbers for Forex pairs
    """
    asset_upper = asset.upper()
    p_str = format_price(asset, price)
    is_forex = False
    if "JPY" in asset_upper or any(fx in asset_upper for fx in ["EUR", "GBP", "AUD", "CAD", "CHF", "NZD"]) or ("USD" in asset_upper and "/" in asset_upper):
        if not any(m in asset_upper for m in ["GOLD", "SILVER", "PLATINUM", "XAU", "XAG", "XPT", "USDT"]):
            is_forex = True
    return p_str if is_forex else f"${p_str}"
