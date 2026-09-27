"""
AI bottrade - Technical Indicators
Clean, high-performance vectorized technical indicators using pure pandas & numpy.
Supports both Crypto and Metals.
"""
import numpy as np
import pandas as pd


def compute_ema(series: pd.Series, span: int) -> pd.Series:
    """Exponential Moving Average."""
    return series.ewm(span=span, adjust=False).mean()


def compute_sma(series: pd.Series, window: int) -> pd.Series:
    """Simple Moving Average."""
    return series.rolling(window=window).mean()


def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    Relative Strength Index (RSI) with Wilder's smoothing.
    """
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    # Wilder's exponential moving average
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()

    rs = avg_gain / (avg_loss + 1e-10)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def compute_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """
    Moving Average Convergence Divergence (MACD).
    Returns (macd_line, signal_line, histogram).
    """
    ema_fast = compute_ema(series, fast)
    ema_slow = compute_ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = compute_ema(macd_line, signal)
    macd_hist = macd_line - signal_line
    return macd_line, signal_line, macd_hist


def compute_bollinger_bands(series: pd.Series, window: int = 20, num_std: float = 2.0):
    """
    Bollinger Bands: Upper, Middle, Lower, Bandwidth, %B.
    """
    middle = compute_sma(series, window)
    std = series.rolling(window=window).std()
    upper = middle + (std * num_std)
    lower = middle - (std * num_std)
    bandwidth = (upper - lower) / (middle + 1e-10)
    pct_b = (series - lower) / (upper - lower + 1e-10)
    return upper, middle, lower, bandwidth, pct_b


def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """
    Average True Range (ATR).
    """
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = true_range.ewm(alpha=1/period, adjust=False).mean()
    return atr


def compute_stochastic(high: pd.Series, low: pd.Series, close: pd.Series, k_period: int = 14, d_period: int = 3):
    """
    Stochastic Oscillator (%K, %D).
    """
    lowest_low = low.rolling(window=k_period).min()
    highest_high = high.rolling(window=k_period).max()
    stoch_k = 100 * ((close - lowest_low) / (highest_high - lowest_low + 1e-10))
    stoch_d = stoch_k.rolling(window=d_period).mean()
    return stoch_k, stoch_d


def compute_adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14):
    """
    Average Directional Index (ADX), +DI, -DI.
    """
    prev_high = high.shift(1)
    prev_low = low.shift(1)

    plus_dm = (high - prev_high).clip(lower=0)
    minus_dm = (prev_low - low).clip(lower=0)

    # When +DM < -DM, +DM = 0; when -DM < +DM, -DM = 0
    mask_plus = plus_dm > minus_dm
    mask_minus = minus_dm > plus_dm
    plus_dm = plus_dm.where(mask_plus, 0.0)
    minus_dm = minus_dm.where(mask_minus, 0.0)

    atr = compute_atr(high, low, close, period)
    smoothed_plus_dm = plus_dm.ewm(alpha=1/period, adjust=False).mean()
    smoothed_minus_dm = minus_dm.ewm(alpha=1/period, adjust=False).mean()

    plus_di = 100 * (smoothed_plus_dm / (atr + 1e-10))
    minus_di = 100 * (smoothed_minus_dm / (atr + 1e-10))

    dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di + 1e-10))
    adx = dx.ewm(alpha=1/period, adjust=False).mean()

    return adx, plus_di, minus_di


def compute_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """
    On-Balance Volume (OBV).
    """
    direction = np.sign(close.diff().fillna(0))
    obv = (direction * volume).cumsum()
    return obv


def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Takes an OHLCV DataFrame and appends all technical indicator columns.
    Expected columns: 'open', 'high', 'low', 'close', 'volume'
    """
    data = df.copy()
    close = data['close']
    high = data['high']
    low = data['low']
    volume = data['volume']

    # EMAs
    data['ema_9'] = compute_ema(close, 9)
    data['ema_21'] = compute_ema(close, 21)
    data['ema_50'] = compute_ema(close, 50)
    data['ema_200'] = compute_ema(close, 200)

    # Relative to EMAs
    data['close_ema_21_ratio'] = close / (data['ema_21'] + 1e-10)
    data['close_ema_200_ratio'] = close / (data['ema_200'] + 1e-10)
    data['ema_trend'] = np.where(data['ema_21'] > data['ema_50'], 1, -1)

    # RSI
    data['rsi'] = compute_rsi(close, 14)
    data['rsi_7'] = compute_rsi(close, 7)

    # MACD
    macd, macd_signal, macd_hist = compute_macd(close, 12, 26, 9)
    data['macd'] = macd
    data['macd_signal'] = macd_signal
    data['macd_hist'] = macd_hist

    # Bollinger Bands
    bb_upper, bb_middle, bb_lower, bb_bandwidth, bb_pct = compute_bollinger_bands(close, 20, 2.0)
    data['bb_upper'] = bb_upper
    data['bb_middle'] = bb_middle
    data['bb_lower'] = bb_lower
    data['bb_bandwidth'] = bb_bandwidth
    data['bb_pct'] = bb_pct

    # ATR
    data['atr'] = compute_atr(high, low, close, 14)
    data['atr_pct'] = data['atr'] / (close + 1e-10)

    # Stochastic Oscillator
    stoch_k, stoch_d = compute_stochastic(high, low, close, 14, 3)
    data['stoch_k'] = stoch_k
    data['stoch_d'] = stoch_d

    # ADX
    adx, plus_di, minus_di = compute_adx(high, low, close, 14)
    data['adx'] = adx
    data['plus_di'] = plus_di
    data['minus_di'] = minus_di

    # Volume Indicators (if volume available and nonzero)
    if 'volume' in data.columns and (data['volume'] > 0).any():
        data['volume_sma_20'] = compute_sma(volume, 20)
        data['volume_ratio'] = volume / (data['volume_sma_20'] + 1e-10)
        data['obv'] = compute_obv(close, volume)
        data['obv_ema'] = compute_ema(data['obv'], 20)
    else:
        data['volume_ratio'] = 1.0
        data['obv'] = 0.0
        data['obv_ema'] = 0.0

    # Momentum / Returns
    data['return_1'] = close.pct_change(1)
    data['return_3'] = close.pct_change(3)
    data['return_5'] = close.pct_change(5)
    data['return_10'] = close.pct_change(10)
    data['volatility_10'] = data['return_1'].rolling(10).std()

    return data
