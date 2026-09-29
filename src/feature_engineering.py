"""
AI bottrade - Feature Engineering & Target Labeling
Generates predictive features and forward-looking targets without lookahead bias.
"""
from typing import List, Optional, Tuple
import numpy as np
import pandas as pd

from src.indicators import add_all_indicators
from src.smc import SMCEngine


class FeatureEngineer:
    def __init__(self, forward_bars: int = 4, target_threshold: Optional[float] = None):
        """
        :param forward_bars: Number of future bars to evaluate target performance
        :param target_threshold: Minimum forward return to classify as BUY (1) or SELL (-1).
                                 If None, automatically adapts dynamically using 0.75 * ATR / Close.
        """
        self.forward_bars = forward_bars
        self.target_threshold = target_threshold
        self.feature_columns: List[str] = []
        self.smc_engine = SMCEngine()

    def prepare_features(self, df: pd.DataFrame, include_target: bool = True) -> Tuple[pd.DataFrame, List[str]]:
        """
        Computes indicators, executes SMC analysis, derives normalized and lagged features,
        and optionally constructs the target label.
        """
        # 1. Technical Indicators
        data = add_all_indicators(df)

        # 2. Smart Money Concepts (SMC) Analysis
        data, _, _ = self.smc_engine.analyze(data)

        # Lagged features for momentum and momentum change
        for col in ['rsi', 'macd_hist', 'return_1', 'volume_ratio']:
            for lag in [1, 2, 3]:
                data[f"{col}_lag_{lag}"] = data[col].shift(lag)

        # Higher-order features
        data['rsi_delta'] = data['rsi'] - data['rsi_lag_1']
        data['macd_delta'] = data['macd_hist'] - data['macd_hist_lag_1']

        # Normalized distances
        data['dist_to_ema21'] = (data['close'] - data['ema_21']) / (data['atr'] + 1e-10)
        data['dist_to_ema200'] = (data['close'] - data['ema_200']) / (data['atr'] + 1e-10)

        # Select feature set (combining Technical Analysis + Smart Money Concepts)
        feature_cols = [
            # Technical Indicators
            'rsi', 'rsi_7', 'rsi_delta',
            'macd', 'macd_signal', 'macd_hist', 'macd_delta',
            'bb_bandwidth', 'bb_pct',
            'atr_pct',
            'stoch_k', 'stoch_d',
            'adx', 'plus_di', 'minus_di',
            'volume_ratio',
            'return_1', 'return_3', 'return_5', 'return_10', 'volatility_10',
            'close_ema_21_ratio', 'close_ema_200_ratio', 'ema_trend',
            'dist_to_ema21', 'dist_to_ema200',
            'rsi_lag_1', 'rsi_lag_2', 'macd_hist_lag_1', 'return_1_lag_1',
            # Smart Money Concepts (SMC) Features
            'smc_structure', 'bos_bullish', 'bos_bearish',
            'choch_bullish', 'choch_bearish',
            'fvg_bullish', 'fvg_bearish',
            'in_bullish_ob', 'in_bearish_ob',
            'sweep_high', 'sweep_low',
            'range_position', 'is_discount', 'is_premium',
            'smc_signal'
        ]

        # Filter out columns that don't exist
        available_features = [col for col in feature_cols if col in data.columns]
        self.feature_columns = available_features

        if include_target:
            # Future return over forward_bars
            future_return = data['close'].shift(-self.forward_bars) / data['close'] - 1.0
            data['future_return'] = future_return

            if self.target_threshold is not None:
                thresh = self.target_threshold
            else:
                # Dynamic volatility-adjusted threshold based on ATR
                # 0.75 * ATR / Close creates natural multi-class balance across 5m, 15m, 1h, Forex, Metals, Crypto
                if 'atr' in data.columns and 'close' in data.columns:
                    thresh = (data['atr'] / data['close']) * 0.75
                else:
                    thresh = 0.002

            # Multi-class target:
            # 1  = BUY  (future return > +threshold)
            # -1 = SELL (future return < -threshold)
            # 0  = HOLD (ranging / neutral)
            conditions = [
                future_return > thresh,
                future_return < -thresh
            ]
            choices = [1, -1]
            data['target'] = np.select(conditions, choices, default=0)

            # Drop rows with NaN from rolling calculations and forward shift
            data = data.dropna(subset=available_features + ['target']).copy()
        else:
            data = data.dropna(subset=available_features).copy()

        return data, available_features
