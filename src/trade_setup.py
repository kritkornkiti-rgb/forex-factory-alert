"""
AI bottrade - Trade Setup & Entry Level Generator
Analyzes institutional SMC structures and AI model confidence to identify:
1. Exact Entry Price & Entry Zones (Order Block / FVG / Market)
2. Exact Stop-Loss Level (Order Block Invalidation / ATR)
3. Exact Take-Profit Targets (TP1: 1:2 R:R, TP2: 1:3 R:R / Opposing Liquidity)
4. Recommended Position Sizing based on risk management
5. SMC Confluence Checklist & Rationale
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from src.config import SUPPORTED_ASSETS, TradingConfig, format_price, format_currency_price
from src.model import AITradingModel


def get_asset_decimals(asset: str) -> int:
    """Returns standard display decimal places for asset"""
    asset_upper = asset.upper()
    if "JPY" in asset_upper:
        return 3
    is_forex = False
    if any(fx in asset_upper for fx in ["EUR", "GBP", "AUD", "CAD", "CHF", "NZD", "=X"]) or ("USD" in asset_upper and "/" in asset_upper):
        if not any(m in asset_upper for m in ["GOLD", "SILVER", "PLATINUM", "XAU", "XAG", "XPT", "USDT"]):
            is_forex = True
    if is_forex:
        return 5
    if "XRP" in asset_upper:
        return 4
    if "SILVER" in asset_upper or "XAG" in asset_upper:
        return 3
    return 2


@dataclass
class TradeSetup:
    asset: str
    timeframe: str
    status: str            # "ACTIVE_SETUP" or "WAITING"
    direction: str         # "BUY (LONG)", "SELL (SHORT)", or "NEUTRAL (WAIT)"
    entry_price: float
    entry_zone: Tuple[float, float]
    entry_type: str        # "MARKET_DISCOUNT", "LIMIT_ORDER_BLOCK", "LIMIT_FVG"
    stop_loss: float
    sl_distance: float
    sl_pct: float
    sl_reason: str
    take_profit_1: float
    tp1_distance: float
    tp1_pct: float
    tp1_rr: float
    take_profit_2: float
    tp2_distance: float
    tp2_pct: float
    tp2_rr: float
    recommended_size: float
    position_value: float
    risk_amount: float
    ai_confidence: float
    confluence_score: int
    total_confluences: int
    confluence_list: List[Dict[str, any]]
    rationale_th: str
    htf_timeframe: Optional[str] = None
    htf_bias: Optional[str] = None
    candlestick_pattern: Optional[str] = None


def evaluate_candlestick_confirmation(df_features: pd.DataFrame, direction: str) -> Tuple[bool, str]:
    """
    Evaluates institutional Price Action / Candlestick Confirmation on the latest bars:
    - Lower/Upper Rejection Wick (Pin bar / Hammer >= 35% wick)
    - Engulfing Candlestick pattern
    - Momentum displacement candle in the trade direction
    - Structural reversal triggers (CHoCH / BOS / Sweep) without strong adverse candle
    """
    if len(df_features) == 0:
        return False, "ไม่มีข้อมูลแท่งเทียน"

    latest = df_features.iloc[-1]
    prev = df_features.iloc[-2] if len(df_features) >= 2 else latest

    c_open = float(latest['open'])
    c_close = float(latest['close'])
    c_high = float(latest['high'])
    c_low = float(latest['low'])
    c_range = max(1e-6, c_high - c_low)
    body = abs(c_close - c_open)

    p_open = float(prev['open'])
    p_close = float(prev['close'])
    p_high = float(prev['high'])
    p_low = float(prev['low'])
    p_range = max(1e-6, p_high - p_low)

    if direction == "BUY":
        # 1. Lower Rejection Wick on current candle (Pin bar / Hammer)
        lower_wick = min(c_open, c_close) - c_low
        wick_ratio = lower_wick / c_range
        if wick_ratio >= 0.35 and c_close >= (c_low + 0.30 * c_range):
            return True, f"แท่งเทียนปฏิเสธราคาต่ำ (Lower Rejection Wick {wick_ratio:.0%}) 🟢"

        # 2. Bullish Engulfing
        if c_close > c_open:
            if c_close > p_high:
                return True, "แท่งเทียน Bullish Engulfing ทะลุ High แท่งก่อนหน้า 🟢"
            elif c_close > p_open and c_open <= p_close and body >= 0.5 * p_range:
                return True, "แท่งเทียน Bullish Engulfing กลืนกินแท่งแดงก่อนหน้า 🟢"

        # 3. Strong Bullish Momentum Candle
        if c_close > c_open and (body / c_range) >= 0.50 and c_close > p_close:
            return True, f"แท่งเทียนโมเมนตัมขาขึ้นเต็มแท่ง (Bullish Momentum Body {body/c_range:.0%}) 🟢"

        # 4. Lower Rejection Wick on PREVIOUS candle + Current is Bullish confirmation
        p_lower_wick = min(p_open, p_close) - p_low
        p_wick_ratio = p_lower_wick / p_range
        if p_wick_ratio >= 0.35 and c_close > c_open:
            return True, f"แท่งก่อนหน้าทิ้งไส้ล่าง (Wick {p_wick_ratio:.0%}) และแท่งปัจจุบันคอนเฟิร์มแรงซื้อ 🟢"

        # 5. SMC Trigger (CHoCH / BOS / Liquidity Sweep Low)
        recent_choch = bool(latest.get('choch_bullish', False)) or bool(prev.get('choch_bullish', False))
        recent_bos = bool(latest.get('bos_bullish', False)) or bool(prev.get('bos_bullish', False))
        recent_sweep = bool(latest.get('sweep_low', False)) or bool(prev.get('sweep_low', False))

        is_dumping = (c_close < c_open) and ((c_open - c_close) / c_range > 0.60)
        if (recent_choch or recent_sweep or recent_bos) and not is_dumping:
            trig_name = "Bullish CHoCH" if recent_choch else ("Sweep Low" if recent_sweep else "Bullish BOS")
            return True, f"เกิดโครงสร้างกลับตัว {trig_name} ยืนยันการเปลี่ยนทิศทาง 🟢"

        return False, "ยังไม่พบแท่งเทียนยืนยันแรงซื้อ (ไม่มี Rejection Wick / Engulfing) แท่งเทียนยังทิ้งตัวลง ⏳"

    elif direction == "SELL":
        # 1. Upper Rejection Wick on current candle (Shooting Star / Bearish Pin)
        upper_wick = c_high - max(c_open, c_close)
        wick_ratio = upper_wick / c_range
        if wick_ratio >= 0.35 and c_close <= (c_high - 0.30 * c_range):
            return True, f"แท่งเทียนปฏิเสธราคาสูง (Upper Rejection Wick {wick_ratio:.0%}) 🔴"

        # 2. Bearish Engulfing
        if c_close < c_open:
            if c_close < p_low:
                return True, "แท่งเทียน Bearish Engulfing หลุด Low แท่งก่อนหน้า 🔴"
            elif c_close < p_open and c_open >= p_close and body >= 0.5 * p_range:
                return True, "แท่งเทียน Bearish Engulfing กลืนกินแท่งเขียวก่อนหน้า 🔴"

        # 3. Strong Bearish Momentum Candle
        if c_close < c_open and (body / c_range) >= 0.50 and c_close < p_close:
            return True, f"แท่งเทียนโมเมนตัมขาลงเต็มแท่ง (Bearish Momentum Body {body/c_range:.0%}) 🔴"

        # 4. Upper Rejection Wick on PREVIOUS candle + Current is Bearish confirmation
        p_upper_wick = p_high - max(p_open, p_close)
        p_wick_ratio = p_upper_wick / p_range
        if p_wick_ratio >= 0.35 and c_close < c_open:
            return True, f"แท่งก่อนหน้าทิ้งไส้บน (Wick {p_wick_ratio:.0%}) และแท่งปัจจุบันคอนเฟิร์มแรงขาย 🔴"

        # 5. SMC Trigger (CHoCH / BOS / Liquidity Sweep High)
        recent_choch = bool(latest.get('choch_bearish', False)) or bool(prev.get('choch_bearish', False))
        recent_bos = bool(latest.get('bos_bearish', False)) or bool(prev.get('bos_bearish', False))
        recent_sweep = bool(latest.get('sweep_high', False)) or bool(prev.get('sweep_high', False))

        is_pumping = (c_close > c_open) and ((c_close - c_open) / c_range > 0.60)
        if (recent_choch or recent_sweep or recent_bos) and not is_pumping:
            trig_name = "Bearish CHoCH" if recent_choch else ("Sweep High" if recent_sweep else "Bearish BOS")
            return True, f"เกิดโครงสร้างกลับตัว {trig_name} ยืนยันการเปลี่ยนทิศทาง 🔴"

        return False, "ยังไม่พบแท่งเทียนยืนยันแรงขาย (ไม่มี Upper Rejection Wick / Bearish Engulfing) แท่งเทียนยังพุ่งขึ้น ⏳"

    return False, "N/A"


class TradeSetupGenerator:
    def __init__(self, config: Optional[TradingConfig] = None):
        self.config = config or TradingConfig()

    def generate_setup(
        self,
        asset_name: str,
        timeframe: str,
        df_features: pd.DataFrame,
        model: AITradingModel,
        capital: float = 10000.0,
        risk_pct: float = 0.02,
        htf_bias: Optional[str] = None,         # "BULLISH", "BEARISH", or None
        htf_timeframe: Optional[str] = None,    # e.g. "15m"
        min_confluence: int = 4                 # User requirement: Confluence >= 4/6
    ) -> TradeSetup:
        """
        Calculates exact trade entry, Stop-Loss, and Take-Profit levels for the latest market bar.
        Enforces HTF Trend Alignment, Minimum Confluence Score (>= 4/6), and Volatility-adaptive SL/TP.
        """
        if df_features.empty:
            raise ValueError("Feature DataFrame cannot be empty.")

        latest = df_features.iloc[-1]
        current_price = float(latest['close'])
        atr = float(latest['atr']) if 'atr' in latest else current_price * 0.01

        # Run AI Model Prediction
        signal, confidence, prob_dict = model.predict_signal(latest)

        # SMC Conditions
        smc_structure = int(latest.get('smc_structure', 1))
        range_pos = float(latest.get('range_position', 0.5))
        is_discount = bool(latest.get('is_discount', range_pos < 0.5))
        is_premium = bool(latest.get('is_premium', range_pos > 0.5))
        in_bull_ob = bool(latest.get('in_bullish_ob', False))
        in_bear_ob = bool(latest.get('in_bearish_ob', False))
        fvg_bull = bool(latest.get('fvg_bullish', False))
        fvg_bear = bool(latest.get('fvg_bearish', False))
        sweep_low = bool(latest.get('sweep_low', False))
        sweep_high = bool(latest.get('sweep_high', False))
        bos_bull = bool(latest.get('bos_bullish', False))
        bos_bear = bool(latest.get('bos_bearish', False))
        choch_bull = bool(latest.get('choch_bullish', False))
        choch_bear = bool(latest.get('choch_bearish', False))

        # Check Confluences
        confluences = []
        confluence_score = 0

        # Confluence 1: Market Structure
        struct_aligned = (signal == 1 and smc_structure == 1) or (signal == -1 and smc_structure == -1)
        confluences.append({
            "name": "Market Structure (โครงสร้างตลาด)",
            "passed": struct_aligned or choch_bull or choch_bear,
            "detail": f"Structure is {'BULLISH 🟢' if smc_structure == 1 else 'BEARISH 🔴'}"
        })
        if struct_aligned or choch_bull or choch_bear:
            confluence_score += 1

        # Confluence 2: Dealing Range (Discount vs Premium)
        range_aligned = (signal == 1 and is_discount) or (signal == -1 and is_premium)
        confluences.append({
            "name": "Dealing Range (โซนราคาได้เปรียบ)",
            "passed": range_aligned,
            "detail": f"{'DISCOUNT (<50%) เหมาะเข้าซื้อ 🟢' if is_discount else 'PREMIUM (>50%) เหมาะขาย 🔴'} ({range_pos*100:.1f}%)"
        })
        if range_aligned:
            confluence_score += 1

        # Confluence 3: Order Block Retest
        ob_aligned = (signal == 1 and in_bull_ob) or (signal == -1 and in_bear_ob)
        confluences.append({
            "name": "Order Block Zone (โซนสถาบัน)",
            "passed": ob_aligned,
            "detail": "ราคาแตะโซน Bullish Order Block" if in_bull_ob else ("ราคาแตะโซน Bearish Order Block" if in_bear_ob else "ไม่มี OB ในระดับราคานี้")
        })
        if ob_aligned:
            confluence_score += 1

        # Confluence 4: Imbalance / FVG
        fvg_aligned = (signal == 1 and fvg_bull) or (signal == -1 and fvg_bear)
        confluences.append({
            "name": "Fair Value Gap (ช่องว่างราคา)",
            "passed": fvg_aligned,
            "detail": "ตรวจพบ Bullish FVG Imbalance" if fvg_bull else ("ตรวจพบ Bearish FVG Imbalance" if fvg_bear else "ราคาอยู่ในสมดุลปกติ")
        })
        if fvg_aligned:
            confluence_score += 1

        # Confluence 5: Liquidity Sweep
        sweep_aligned = (signal == 1 and sweep_low) or (signal == -1 and sweep_high)
        confluences.append({
            "name": "Liquidity Sweep (กวาดสภาพคล่อง)",
            "passed": sweep_aligned,
            "detail": "เกิด Sell-side Liquidity Sweep ใต้ Low 🟢" if sweep_low else ("เกิด Buy-side Liquidity Sweep เหนือ High 🔴" if sweep_high else "ไม่มีการ Sweep")
        })
        if sweep_aligned:
            confluence_score += 1

        # Confluence 6: AI Confidence
        ai_aligned = (confidence >= model.confidence_threshold) and (signal != 0)
        confluences.append({
            "name": "AI Model Confidence (ความมั่นใจของ AI)",
            "passed": ai_aligned,
            "detail": f"AI มั่นใจ {confidence:.1%} (เกณฑ์ขั้นต่ำ: {model.confidence_threshold:.1%})"
        })
        if ai_aligned:
            confluence_score += 1

        recent_swing_lows = df_features[df_features['is_swing_low']].tail(3)
        recent_swing_highs = df_features[df_features['is_swing_high']].tail(3)

        # Raw Candidate Setup
        raw_buy = (signal == 1 or prob_dict.get('BUY', 0.0) >= 0.40) and (is_discount or in_bull_ob or struct_aligned)
        raw_sell = (signal == -1 or prob_dict.get('SELL', 0.0) >= 0.40) and (is_premium or in_bear_ob or struct_aligned)

        # Candlestick Confirmation Evaluation
        bull_confirmed, bull_candle_desc = evaluate_candlestick_confirmation(df_features, "BUY")
        bear_confirmed, bear_candle_desc = evaluate_candlestick_confirmation(df_features, "SELL")

        # Confluence 7: Candlestick Confirmation (แท่งเทียนยืนยันแรงซื้อ/ขาย)
        candle_aligned = (signal == 1 and bull_confirmed) or (signal == -1 and bear_confirmed) or (raw_buy and bull_confirmed) or (raw_sell and bear_confirmed)
        candle_detail = bull_candle_desc if (raw_buy or signal == 1) else (bear_candle_desc if (raw_sell or signal == -1) else "ยังไม่มีการคอนเฟิร์มแท่งเทียน")
        confluences.append({
            "name": "Candlestick Confirmation (แท่งเทียนยืนยันแรงซื้อ/ขาย)",
            "passed": candle_aligned,
            "detail": candle_detail
        })
        if candle_aligned:
            confluence_score += 1

        total_confluences = len(confluences)

        # Filter 1: Minimum Confluence Score (>= 4/7)
        meets_confluence = (confluence_score >= min_confluence)

        # Filter 2: Higher Timeframe (HTF) Alignment Filter
        htf_filter_rejected = False
        htf_rejection_reason = ""
        htf_confirmed_str = ""

        if htf_bias:
            htf_bias_upper = htf_bias.upper()
            tf_label = htf_timeframe or "HTF"
            if raw_buy and "BEARISH" in htf_bias_upper:
                htf_filter_rejected = True
                htf_rejection_reason = f"สัญญาณ BUY ในกรอบ {timeframe} ถูกกรองออกเนื่องจากขัดแย้งกับแนวโน้ม HTF ({tf_label}) ที่เป็น BEARISH 🔴 (สถาบันเน้น Sell ตามภาพใหญ่)"
            elif raw_sell and "BULLISH" in htf_bias_upper:
                htf_filter_rejected = True
                htf_rejection_reason = f"สัญญาณ SELL ในกรอบ {timeframe} ถูกกรองออกเนื่องจากขัดแย้งกับแนวโน้ม HTF ({tf_label}) ที่เป็น BULLISH 🟢 (สถาบันเน้น Buy ตามภาพใหญ่)"
            elif raw_buy and "BULLISH" in htf_bias_upper:
                htf_confirmed_str = f" [HTF {tf_label}: BULLISH 🟢 สอดคล้องภาพใหญ่]"
            elif raw_sell and "BEARISH" in htf_bias_upper:
                htf_confirmed_str = f" [HTF {tf_label}: BEARISH 🔴 สอดคล้องภาพใหญ่]"

        # Filter 3: Candlestick Confirmation is MANDATORY for active execution
        is_buy_setup = raw_buy and meets_confluence and not htf_filter_rejected and bull_confirmed
        is_sell_setup = raw_sell and meets_confluence and not htf_filter_rejected and bear_confirmed

        candle_unconfirmed = False
        candle_unconfirmed_reason = ""
        if raw_buy and meets_confluence and not htf_filter_rejected and not bull_confirmed:
            candle_unconfirmed = True
            candle_unconfirmed_reason = f"สัญญาณ BUY ในกรอบ {timeframe} อยู่ในโซน Discount และผ่านเกณฑ์ SMC แต่ 'ยังไม่พบแท่งเทียนยืนยันแรงซื้อ' ({bull_candle_desc}) -> ระบบ WAIT เพื่อป้องกันการรับมีด (Falling Knife)"
        elif raw_sell and meets_confluence and not htf_filter_rejected and not bear_confirmed:
            candle_unconfirmed = True
            candle_unconfirmed_reason = f"สัญญาณ SELL ในกรอบ {timeframe} อยู่ในโซน Premium และผ่านเกณฑ์ SMC แต่ 'ยังไม่พบแท่งเทียนยืนยันแรงขาย' ({bear_candle_desc}) -> ระบบ WAIT เพื่อป้องกันการ Sell สวนแรงซื้อที่กำลังพุ่ง"

        dec = get_asset_decimals(asset_name)
        candlestick_pattern = None

        if is_buy_setup:
            direction = "BUY (LONG)"
            status = "ACTIVE_SETUP"
            candlestick_pattern = bull_candle_desc

            # Entry Level
            entry_price = current_price
            entry_zone = (round(current_price * 0.998, dec), round(current_price * 1.001, dec))
            entry_type = "MARKET_DISCOUNT" if is_discount else "SMC_CONFIRMATION"

            # Unified SL: Check if there is an SMC Swing Low or Order Block base nearby
            default_atr_sl_dist = max(atr * self.config.sl_atr_multiplier, current_price * 0.004)
            chosen_sl_dist = default_atr_sl_dist
            sl_reason = f"คำนวณตามความผันผวน Dynamic ATR ({self.config.sl_atr_multiplier}x ATR = {format_currency_price(asset_name, default_atr_sl_dist)})"

            if not recent_swing_lows.empty:
                last_sl_price = float(recent_swing_lows['low'].iloc[-1])
                # Invalidation buffer: 0.15 x ATR below the structural low
                structural_sl = last_sl_price - (0.15 * atr)
                dist_from_entry = entry_price - structural_sl

                # Ensure structural SL is logically valid (below entry and within 0.5x to 2.5x ATR)
                if 0.5 * atr < dist_from_entry < 2.5 * default_atr_sl_dist:
                    chosen_sl_dist = dist_from_entry
                    sl_reason = f"วางใต้ขอบล่าง SMC Swing Low / Order Block ({format_currency_price(asset_name, last_sl_price)}) + บัฟเฟอร์ความผันผวน 0.15x ATR"

            stop_loss = entry_price - chosen_sl_dist
            sl_distance = chosen_sl_dist
            sl_pct = (chosen_sl_dist / entry_price) * 100

            # Take Profit Targets based on actual SL risk (R:R 1:2 and 1:3)
            tp1_distance = chosen_sl_dist * 2.0  # 1:2 R:R
            take_profit_1 = entry_price + tp1_distance
            tp1_pct = (tp1_distance / entry_price) * 100
            tp1_rr = 2.0

            tp2_distance = chosen_sl_dist * 3.0  # 1:3 R:R
            take_profit_2 = entry_price + tp2_distance
            tp2_pct = (tp2_distance / entry_price) * 100
            tp2_rr = 3.0

            # Position Sizing based on risk
            risk_dollars = capital * risk_pct
            size = risk_dollars / chosen_sl_dist
            pos_value = size * entry_price

            p_entry = format_currency_price(asset_name, entry_price)
            p_sl = format_currency_price(asset_name, stop_loss)
            p_tp1 = format_currency_price(asset_name, take_profit_1)

            rationale = (
                f"สัญญาณ BUY เกิดขึ้นเนื่องจากราคาอยู่ในโซน DISCOUNT ({range_pos*100:.1f}%) "
                f"และโครงสร้างตลาดเป็นขาขึ้น (BULLISH) โดยโมเดล AI ให้ความน่าจะเป็น {prob_dict.get('BUY', 0.0):.1%}"
                f"{htf_confirmed_str} [คอนเฟิร์ม: {bull_candle_desc}] "
                f"แนะนำเปิดสถานะ LONG ที่ราคา {p_entry} โดยมีจุดตัดขาดทุน (SL) ที่ {p_sl} "
                f"({sl_reason}) และเป้าหมายทำกำไรหลัก (TP1) ที่ {p_tp1} (R:R 1:2.0)"
            )

        elif is_sell_setup:
            direction = "SELL (SHORT)"
            status = "ACTIVE_SETUP"
            candlestick_pattern = bear_candle_desc

            entry_price = current_price
            entry_zone = (round(current_price * 0.999, dec), round(current_price * 1.002, dec))
            entry_type = "MARKET_PREMIUM" if is_premium else "SMC_CONFIRMATION"

            default_atr_sl_dist = max(atr * self.config.sl_atr_multiplier, current_price * 0.004)
            chosen_sl_dist = default_atr_sl_dist
            sl_reason = f"คำนวณตามความผันผวน Dynamic ATR ({self.config.sl_atr_multiplier}x ATR = {format_currency_price(asset_name, default_atr_sl_dist)})"

            if not recent_swing_highs.empty:
                last_sh_price = float(recent_swing_highs['high'].iloc[-1])
                structural_sl = last_sh_price + (0.15 * atr)
                dist_from_entry = structural_sl - entry_price

                if 0.5 * atr < dist_from_entry < 2.5 * default_atr_sl_dist:
                    chosen_sl_dist = dist_from_entry
                    sl_reason = f"วางเหนือขอบบน SMC Swing High / Order Block ({format_currency_price(asset_name, last_sh_price)}) + บัฟเฟอร์ความผันผวน 0.15x ATR"

            stop_loss = entry_price + chosen_sl_dist
            sl_distance = chosen_sl_dist
            sl_pct = (chosen_sl_dist / entry_price) * 100

            tp1_distance = chosen_sl_dist * 2.0
            take_profit_1 = entry_price - tp1_distance
            tp1_pct = (tp1_distance / entry_price) * 100
            tp1_rr = 2.0

            tp2_distance = chosen_sl_dist * 3.0
            take_profit_2 = entry_price - tp2_distance
            tp2_pct = (tp2_distance / entry_price) * 100
            tp2_rr = 3.0

            risk_dollars = capital * risk_pct
            size = risk_dollars / chosen_sl_dist
            pos_value = size * entry_price

            p_entry = format_currency_price(asset_name, entry_price)
            p_sl = format_currency_price(asset_name, stop_loss)
            p_tp1 = format_currency_price(asset_name, take_profit_1)

            rationale = (
                f"สัญญาณ SELL เกิดขึ้นเนื่องจากราคาอยู่ในโซน PREMIUM ({range_pos*100:.1f}%) "
                f"และโครงสร้างตลาดเป็นขาลง (BEARISH) โดยโมเดล AI ให้ความน่าจะเป็น {prob_dict.get('SELL', 0.0):.1%}"
                f"{htf_confirmed_str} [คอนเฟิร์ม: {bear_candle_desc}] "
                f"แนะนำเปิดสถานะ SHORT ที่ราคา {p_entry} โดยมีจุดตัดขาดทุน (SL) ที่ {p_sl} "
                f"({sl_reason}) และเป้าหมายทำกำไรหลัก (TP1) ที่ {p_tp1} (R:R 1:2.0)"
            )

        else:
            direction = "NEUTRAL (WAIT)"
            status = "WAITING"
            entry_price = current_price
            entry_zone = (current_price, current_price)
            entry_type = "NONE"
            stop_loss = 0.0
            sl_distance = 0.0
            sl_pct = 0.0
            take_profit_1 = 0.0
            tp1_distance = 0.0
            tp1_pct = 0.0
            tp1_rr = 0.0
            take_profit_2 = 0.0
            tp2_distance = 0.0
            tp2_pct = 0.0
            tp2_rr = 0.0
            size = 0.0
            pos_value = 0.0
            risk_dollars = 0.0

            if htf_filter_rejected:
                sl_reason = f"กรองออกโดย HTF Alignment ({htf_timeframe or 'HTF'})"
                rationale = htf_rejection_reason
            elif candle_unconfirmed:
                sl_reason = "รอแท่งเทียนยืนยันการกลับตัว (Candle Confirmation)"
                rationale = candle_unconfirmed_reason
            elif not meets_confluence and (raw_buy or raw_sell):
                cand_dir = "BUY" if raw_buy else "SELL"
                sl_reason = f"Confluence ไม่ผ่านเกณฑ์ ({confluence_score}/{total_confluences} < {min_confluence})"
                rationale = (
                    f"ตรวจพบสัญญาณ {cand_dir} แต่ Confluence ไม่ผ่านเกณฑ์ขั้นต่ำ ({confluence_score}/{total_confluences} ข้อ - ต้องการอย่างน้อย {min_confluence}/{total_confluences}) "
                    f"ระบบกรองออกเพื่อลดสัญญาณหลอก (Noise) ในกรอบ {timeframe}"
                )
            else:
                sl_reason = "ตลาดอยู่ในช่วงสภาวะพักตัวหรือยังไม่เข้าเงื่อนไข SMC"
                rationale = f"ขณะนี้ตลาดยังไม่มี Setup ที่มี Confluence ครบถ้วน (เกณฑ์ ≥{min_confluence}/{total_confluences}) AI แนะนำให้อยู่ในสถานะ WAIT เพื่อรอจังหวะที่ดีที่สุด"

        return TradeSetup(
            asset=asset_name,
            timeframe=timeframe,
            status=status,
            direction=direction,
            entry_price=round(entry_price, dec),
            entry_zone=entry_zone,
            entry_type=entry_type,
            stop_loss=round(stop_loss, dec),
            sl_distance=round(sl_distance, dec),
            sl_pct=round(sl_pct, 2),
            sl_reason=sl_reason,
            take_profit_1=round(take_profit_1, dec),
            tp1_distance=round(tp1_distance, dec),
            tp1_pct=round(tp1_pct, 2),
            tp1_rr=tp1_rr,
            take_profit_2=round(take_profit_2, dec),
            tp2_distance=round(tp2_distance, dec),
            tp2_pct=round(tp2_pct, 2),
            tp2_rr=tp2_rr,
            recommended_size=round(size, 4),
            position_value=round(pos_value, 2),
            risk_amount=round(risk_dollars, 2),
            ai_confidence=round(confidence, 4),
            confluence_score=confluence_score,
            total_confluences=total_confluences,
            confluence_list=confluences,
            rationale_th=rationale,
            htf_timeframe=htf_timeframe,
            htf_bias=htf_bias,
            candlestick_pattern=candlestick_pattern
        )
