"""
AI bottrade - Data Loader
Fetches historical and real-time market data for Crypto and Precious Metals.
Supports CCXT (Binance) and Yahoo Finance (yfinance) with smart caching.
"""
from datetime import datetime, timedelta
import logging
from pathlib import Path
from typing import Optional
import pandas as pd

from src.config import DATA_DIR, SUPPORTED_ASSETS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AI-bottrade-data")


class MarketDataLoader:
    def __init__(self, cache_dir: Path = DATA_DIR):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _slugify(text: str) -> str:
        return text.replace("/", "_").replace("=", "_").replace(" ", "_").replace("(", "").replace(")", "").lower()

    def fetch_data(
        self,
        asset_name: str,
        timeframe: str = "1h",
        limit: Optional[int] = 2000,
        force_download: bool = False
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data for the given asset and timeframe.
        Attempts CCXT for crypto or yfinance for metals, with fallback and caching.
        """
        if asset_name not in SUPPORTED_ASSETS:
            raise ValueError(f"Asset '{asset_name}' not recognized. Choose from: {list(SUPPORTED_ASSETS.keys())}")

        asset_info = SUPPORTED_ASSETS[asset_name]
        slug = self._slugify(asset_name)
        cache_file = self.cache_dir / f"{slug}_{timeframe}.csv"

        # Check local cache first if not forced
        if not force_download and cache_file.exists():
            try:
                cached_df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
                if len(cached_df) >= 100:
                    logger.info(f"Loaded {len(cached_df)} rows for {asset_name} ({timeframe}) from cache.")
                    return cached_df
            except Exception as e:
                logger.warning(f"Cache read error: {e}. Refetching...")

        df = None
        # Attempt primary source
        if asset_info["category"] == "crypto":
            df = self._fetch_crypto(asset_info, timeframe, limit)
            if df is None or df.empty:
                logger.warning(f"CCXT fetch failed for {asset_name}, falling back to Yahoo Finance...")
                df = self._fetch_yfinance(asset_info.get("yfinance_symbol", "BTC-USD"), timeframe, limit)
        else:
            # Metals or commodities
            symbol = asset_info.get("symbol", "GC=F")
            df = self._fetch_yfinance(symbol, timeframe, limit)
            if df is None or df.empty:
                alt_sym = asset_info.get("alt_symbol")
                if alt_sym:
                    logger.info(f"Retrying with alternative symbol {alt_sym}...")
                    df = self._fetch_yfinance(alt_sym, timeframe, limit)

        if df is None or df.empty:
            raise RuntimeError(f"Could not retrieve data for {asset_name} ({timeframe})")

        # Standardize columns
        df = self._clean_ohlcv(df)

        # Save to cache
        try:
            df.to_csv(cache_file)
            logger.info(f"Cached {len(df)} records to {cache_file.name}")
        except Exception as e:
            logger.warning(f"Failed to cache data: {e}")

        return df

    def _fetch_crypto(self, asset_info: dict, timeframe: str, limit: int) -> Optional[pd.DataFrame]:
        try:
            import ccxt
            exchange = ccxt.binance({
                'enableRateLimit': True,
                'timeout': 10000,
            })
            symbol = asset_info["symbol"]
            tf_map = {"15m": "15m", "1h": "1h", "4h": "4h", "1d": "1d"}
            ccxt_tf = tf_map.get(timeframe, "1h")

            logger.info(f"Fetching {symbol} from Binance via CCXT ({ccxt_tf}, limit={limit})...")
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe=ccxt_tf, limit=limit)
            if not ohlcv:
                return None

            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('datetime', inplace=True)
            df.drop(columns=['timestamp'], inplace=True)
            return df
        except Exception as e:
            logger.warning(f"CCXT error: {e}")
            return None

    def _fetch_yfinance(self, ticker: str, timeframe: str, limit: int) -> Optional[pd.DataFrame]:
        try:
            import yfinance as yf
            # Map timeframe to yfinance interval and valid period
            yf_map = {
                "15m": ("15m", "50d"),
                "1h": ("1h", "700d"),
                "4h": ("1h", "700d"),  # Will resample to 4h
                "1d": ("1d", "5y"),
            }
            interval, period = yf_map.get(timeframe, ("1h", "700d"))
            logger.info(f"Fetching {ticker} from Yahoo Finance (interval={interval}, period={period})...")
            
            data = yf.download(ticker, interval=interval, period=period, progress=False, auto_adjust=True)
            if data is None or data.empty:
                return None

            # Handle multi-level columns if present in recent yfinance
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = [col[0].lower() for col in data.columns]
            else:
                data.columns = [c.lower() for c in data.columns]

            if timeframe == "4h":
                # Resample 1h to 4h
                data = data.resample('4h').agg({
                    'open': 'first',
                    'high': 'max',
                    'low': 'min',
                    'close': 'last',
                    'volume': 'sum'
                }).dropna()

            if limit and len(data) > limit:
                data = data.iloc[-limit:]

            return data
        except Exception as e:
            logger.warning(f"yfinance error for {ticker}: {e}")
            return None

    @staticmethod
    def _clean_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
        clean = df.copy()
        clean.columns = [c.lower() for c in clean.columns]
        required = ['open', 'high', 'low', 'close', 'volume']
        for col in required:
            if col not in clean.columns:
                if col == 'volume':
                    clean['volume'] = 0.0
                else:
                    raise ValueError(f"Missing required column: {col}")
            clean[col] = pd.to_numeric(clean[col], errors='coerce')

        clean.dropna(subset=['open', 'high', 'low', 'close'], inplace=True)
        clean = clean[~clean.index.duplicated(keep='first')]
        clean.sort_index(inplace=True)
        return clean
