"""
AI bottrade - Smart Money Concepts (SMC) Engine
Implements institutional trading logic:
- Market Structure (BOS: Break of Structure, CHoCH: Change of Character)
- Order Blocks (Bullish & Bearish OB with Mitigation tracking)
- Fair Value Gaps (Bullish & Bearish FVG / Imbalance)
- Liquidity Sweeps (Buy-side & Sell-side Liquidity Runs)
- Premium vs. Discount Equilibrium Zones (OTE: Optimal Trade Entry)
"""
from dataclasses import dataclass
from typing import List, Optional, Tuple
import numpy as np
import pandas as pd


@dataclass
class OrderBlock:
    index: int
    timestamp: any
    type: str  # "BULLISH" or "BEARISH"
    top: float
    bottom: float
    mitigated: bool = False
    mitigated_index: Optional[int] = None


@dataclass
class FairValueGap:
    index: int
    timestamp: any
    type: str  # "BULLISH" or "BEARISH"
    top: float
    bottom: float
    mitigated: bool = False


class SMCEngine:
    def __init__(self, swing_window: int = 4, fvg_threshold_atr: float = 0.5):
        """
        :param swing_window: Bars to look left and right for fractal swing points
        :param fvg_threshold_atr: Minimum gap size relative to ATR to qualify as institutional FVG
        """
        self.swing_window = swing_window
        self.fvg_threshold_atr = fvg_threshold_atr

    def analyze(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[OrderBlock], List[FairValueGap]]:
        """
        Performs full Smart Money Concepts analysis on the given OHLCV DataFrame.
        Returns:
            - DataFrame with added SMC indicator columns
            - List of active/recent Order Blocks
            - List of active/recent Fair Value Gaps
        """
        data = df.copy()
        n = len(data)

        # 1. Detect Swing Highs and Swing Lows (Fractals)
        highs = data['high'].values
        lows = data['low'].values
        closes = data['close'].values
        opens = data['open'].values
        timestamps = data.index

        is_swing_high = np.zeros(n, dtype=bool)
        is_swing_low = np.zeros(n, dtype=bool)
        w = self.swing_window

        for i in range(w, n - w):
            if all(highs[i] >= highs[i - k] for k in range(1, w + 1)) and \
               all(highs[i] > highs[i + k] for k in range(1, w + 1)):
                is_swing_high[i] = True

            if all(lows[i] <= lows[i - k] for k in range(1, w + 1)) and \
               all(lows[i] < lows[i + k] for k in range(1, w + 1)):
                is_swing_low[i] = True

        data['is_swing_high'] = is_swing_high
        data['is_swing_low'] = is_swing_low

        # 2. Market Structure (BOS & CHoCH)
        # Tracking structure: 1 for Bullish, -1 for Bearish
        structure = np.zeros(n, dtype=int)
        bos_bullish = np.zeros(n, dtype=bool)
        bos_bearish = np.zeros(n, dtype=bool)
        choch_bullish = np.zeros(n, dtype=bool)
        choch_bearish = np.zeros(n, dtype=bool)

        last_sh_price = highs[0]
        last_sl_price = lows[0]
        current_trend = 1

        for i in range(1, n):
            # Update last confirmed swing points
            if is_swing_high[i - 1]:
                last_sh_price = highs[i - 1]
            if is_swing_low[i - 1]:
                last_sl_price = lows[i - 1]

            close = closes[i]

            if current_trend == 1:
                # In uptrend: Breaking swing high is BOS (Continuation)
                if close > last_sh_price:
                    bos_bullish[i] = True
                    last_sh_price = highs[i]
                # In uptrend: Breaking swing low is CHoCH (Trend Reversal to Bearish)
                elif close < last_sl_price:
                    choch_bearish[i] = True
                    current_trend = -1
                    last_sl_price = lows[i]
            else:
                # In downtrend: Breaking swing low is BOS (Continuation)
                if close < last_sl_price:
                    bos_bearish[i] = True
                    last_sl_price = lows[i]
                # In downtrend: Breaking swing high is CHoCH (Trend Reversal to Bullish)
                elif close > last_sh_price:
                    choch_bullish[i] = True
                    current_trend = 1
                    last_sh_price = highs[i]

            structure[i] = current_trend

        data['smc_structure'] = structure
        data['bos_bullish'] = bos_bullish
        data['bos_bearish'] = bos_bearish
        data['choch_bullish'] = choch_bullish
        data['choch_bearish'] = choch_bearish

        # 3. Fair Value Gaps (FVG)
        fvg_bullish = np.zeros(n, dtype=bool)
        fvg_bearish = np.zeros(n, dtype=bool)
        fvg_list: List[FairValueGap] = []

        for i in range(2, n):
            # Bullish FVG: Low of candle i > High of candle i-2
            if lows[i] > highs[i - 2]:
                gap_size = lows[i] - highs[i - 2]
                if gap_size > 0:
                    fvg_bullish[i] = True
                    fvg_list.append(FairValueGap(
                        index=i,
                        timestamp=timestamps[i],
                        type="BULLISH",
                        top=lows[i],
                        bottom=highs[i - 2]
                    ))

            # Bearish FVG: High of candle i < Low of candle i-2
            elif highs[i] < lows[i - 2]:
                gap_size = lows[i - 2] - highs[i]
                if gap_size > 0:
                    fvg_bearish[i] = True
                    fvg_list.append(FairValueGap(
                        index=i,
                        timestamp=timestamps[i],
                        type="BEARISH",
                        top=lows[i - 2],
                        bottom=highs[i]
                    ))

        # Check FVG mitigation
        for fvg in fvg_list:
            for j in range(fvg.index + 1, n):
                if fvg.type == "BULLISH":
                    if lows[j] <= fvg.bottom:
                        fvg.mitigated = True
                        break
                else:
                    if highs[j] >= fvg.top:
                        fvg.mitigated = True
                        break

        data['fvg_bullish'] = fvg_bullish
        data['fvg_bearish'] = fvg_bearish

        # 4. Order Blocks (OB)
        order_blocks: List[OrderBlock] = []
        ob_bullish_flag = np.zeros(n, dtype=bool)
        ob_bearish_flag = np.zeros(n, dtype=bool)

        for i in range(2, n):
            # Bullish OB: Last down candle before an impulsive move that created BOS or Bullish FVG
            if (bos_bullish[i] or fvg_bullish[i]):
                # Look back up to 5 bars for the last down candle
                for k in range(i - 1, max(0, i - 6), -1):
                    if closes[k] < opens[k]:
                        ob = OrderBlock(
                            index=k,
                            timestamp=timestamps[k],
                            type="BULLISH",
                            top=max(opens[k], closes[k]),
                            bottom=lows[k]
                        )
                        order_blocks.append(ob)
                        ob_bullish_flag[k] = True
                        break

            # Bearish OB: Last up candle before an impulsive move that created BOS or Bearish FVG
            if (bos_bearish[i] or fvg_bearish[i]):
                for k in range(i - 1, max(0, i - 6), -1):
                    if closes[k] > opens[k]:
                        ob = OrderBlock(
                            index=k,
                            timestamp=timestamps[k],
                            type="BEARISH",
                            top=highs[k],
                            bottom=min(opens[k], closes[k])
                        )
                        order_blocks.append(ob)
                        ob_bearish_flag[k] = True
                        break

        # Track OB mitigation
        for ob in order_blocks:
            for j in range(ob.index + 1, n):
                if ob.type == "BULLISH":
                    # Price entered the OB zone
                    if lows[j] <= ob.top and closes[j] >= ob.bottom:
                        ob.mitigated = True
                        ob.mitigated_index = j
                    # Invalidation: price closed below OB bottom
                    elif closes[j] < ob.bottom:
                        ob.mitigated = True
                        ob.mitigated_index = j
                        break
                else:
                    if highs[j] >= ob.bottom and closes[j] <= ob.top:
                        ob.mitigated = True
                        ob.mitigated_index = j
                    elif closes[j] > ob.top:
                        ob.mitigated = True
                        ob.mitigated_index = j
                        break

        # 5. Liquidity Sweeps
        sweep_high = np.zeros(n, dtype=bool)
        sweep_low = np.zeros(n, dtype=bool)

        for i in range(1, n):
            # Sweep High: price wicks above last swing high but closes below it
            if highs[i] > last_sh_price and closes[i] < last_sh_price:
                sweep_high[i] = True
            # Sweep Low: price wicks below last swing low but closes above it
            if lows[i] < last_sl_price and closes[i] > last_sl_price:
                sweep_low[i] = True

        data['sweep_high'] = sweep_high
        data['sweep_low'] = sweep_low

        # 6. Premium vs Discount Equilibrium
        # Calculate recent 20-bar range equilibrium
        rolling_high = data['high'].rolling(30).max()
        rolling_low = data['low'].rolling(30).min()
        equilibrium = (rolling_high + rolling_low) / 2.0
        data['equilibrium'] = equilibrium
        # Range position: 0 (bottom) to 1.0 (top)
        range_pos = (closes - rolling_low) / (rolling_high - rolling_low + 1e-10)
        data['range_position'] = range_pos
        data['is_discount'] = range_pos < 0.5  # Optimal for buying
        data['is_premium'] = range_pos > 0.5   # Optimal for selling

        # Check if current price is tapping into an active Bullish or Bearish OB
        in_bullish_ob = np.zeros(n, dtype=bool)
        in_bearish_ob = np.zeros(n, dtype=bool)

        for ob in order_blocks:
            for j in range(ob.index + 1, n):
                if ob.mitigated_index is not None and j > ob.mitigated_index:
                    continue
                if ob.type == "BULLISH" and lows[j] <= ob.top and closes[j] >= ob.bottom:
                    in_bullish_ob[j] = True
                elif ob.type == "BEARISH" and highs[j] >= ob.bottom and closes[j] <= ob.top:
                    in_bearish_ob[j] = True

        data['in_bullish_ob'] = in_bullish_ob
        data['in_bearish_ob'] = in_bearish_ob

        # 7. SMC High-Probability Confluence Signal
        # Bullish Setup: Bullish Structure + Discount Zone + (In Bullish OB OR In Bullish FVG OR Swept Low)
        smc_buy = (data['smc_structure'] == 1) & (data['is_discount']) & (
            data['in_bullish_ob'] | data['fvg_bullish'] | data['sweep_low'] | data['choch_bullish']
        )

        # Bearish Setup: Bearish Structure + Premium Zone + (In Bearish OB OR In Bearish FVG OR Swept High)
        smc_sell = (data['smc_structure'] == -1) & (data['is_premium']) & (
            data['in_bearish_ob'] | data['fvg_bearish'] | data['sweep_high'] | data['choch_bearish']
        )

        smc_signal = np.zeros(n, dtype=int)
        smc_signal[smc_buy] = 1
        smc_signal[smc_sell] = -1
        data['smc_signal'] = smc_signal

        return data, order_blocks, fvg_list
