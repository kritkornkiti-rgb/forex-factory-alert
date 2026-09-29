"""
AI bottrade - 24/7 Live Market Monitor & Auto-Alert Engine
Continuously tracks market price action, detects institutional SMC setups,
manages open positions (SL/TP alerts), and broadcasts real-time notifications.
"""
from datetime import datetime
import json
import logging
from pathlib import Path
import time
from typing import Dict, List, Optional, Tuple
import pandas as pd

from src.config import DATA_DIR, MODELS_DIR, SUPPORTED_ASSETS, TradingConfig, format_currency_price
from src.data_loader import MarketDataLoader
from src.feature_engineering import FeatureEngineer
from src.model import AITradingModel
from src.notifier import AlertNotifier
from src.paper_trader import PaperTrader
from src.trade_setup import TradeSetup, TradeSetupGenerator

logger = logging.getLogger("AI-bottrade-monitor")


HTF_TIMEFRAME_MAP = {
    "5m": "15m",   # User requirement: M5 uses M15 as HTF
    "15m": "1h",
    "1h": "4h",
    "4h": "1d",
}


class LiveMarketMonitor:
    def __init__(
        self,
        assets: Optional[List[str]] = None,
        timeframe: Optional[str] = None,
        timeframes: Optional[List[str]] = None,
        check_interval_seconds: int = 60,
        enable_paper_trade: bool = True
    ):
        self.assets = assets or ["GOLD (XAU/USD)", "BTC/USDT"]
        if timeframes:
            self.timeframes = timeframes
        elif timeframe:
            if "," in timeframe:
                self.timeframes = [t.strip() for t in timeframe.split(",")]
            else:
                self.timeframes = [timeframe]
        else:
            self.timeframes = ["1h"]

        self.timeframe = self.timeframes[0]
        self.interval = check_interval_seconds
        self.enable_paper_trade = enable_paper_trade

        self.config_file = DATA_DIR / "monitor_config.json"
        self.load_config(initial=True)
        if assets:
            self.assets = assets
        if timeframes:
            self.timeframes = timeframes
        elif timeframe:
            if "," in timeframe:
                self.timeframes = [t.strip() for t in timeframe.split(",")]
            else:
                self.timeframes = [timeframe]
        self.timeframe = self.timeframes[0] if self.timeframes else "1h"

        self.data_loader = MarketDataLoader()
        self.feature_engineer = FeatureEngineer()
        self.notifier = AlertNotifier()
        self.setup_gen = TradeSetupGenerator()

        self.log_file = DATA_DIR / "monitor_activity.json"
        self.status_file = DATA_DIR / "monitor_status.json"

        # Cooldown settings: 30-minute Directional Cooldown (User requirement 3)
        self.cooldown_seconds: int = 1800
        self.alert_history: Dict[str, dict] = {}  # cache_key -> {direction, timestamp, candle_time, price}
        self.htf_cache: Dict[str, dict] = {}      # cache_key -> {timestamp, bias, structure, close, ema50}

        # Cooldown cache: (asset_tf) -> candle_time
        self.alerted_candles: Dict[str, str] = {}
        self.is_running = False

    def load_config(self, initial: bool = False):
        """Loads persistent monitor settings (assets, timeframes, interval) if available"""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r") as f:
                    cfg = json.load(f)
                    new_assets = cfg.get("assets", getattr(self, "assets", ["GOLD (XAU/USD)", "BTC/USDT"]))
                    new_tfs = cfg.get("timeframes", getattr(self, "timeframes", ["1h"]))
                    new_interval = cfg.get("interval", getattr(self, "interval", 60))

                    if not initial and hasattr(self, "assets") and hasattr(self, "timeframes"):
                        if set(new_assets) != set(self.assets) or set(new_tfs) != set(self.timeframes):
                            print(f"\n⚡ [Dashboard Update Detected] อัปเดตรายการเฝ้ากราฟจากหน้าเว็บทันที:")
                            print(f"   📊 สินทรัพย์: {', '.join(new_assets)}")
                            print(f"   ⏱️ Timeframes: {', '.join(new_tfs)}\n")
                            logger.info(f"Monitor updated: {new_assets} | {new_tfs}")

                    self.assets = new_assets
                    self.timeframes = new_tfs
                    self.interval = new_interval
                    if self.timeframes:
                        self.timeframe = self.timeframes[0]
            except Exception as e:
                logger.warning(f"Failed to read monitor config: {e}")

    def get_htf_bias(self, asset: str, tf: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Determines Higher Timeframe (HTF) market bias for the given asset and timeframe.
        Specifically, for 5m it evaluates 15m structure and trend.
        Returns: (bias, htf_timeframe) e.g. ("BULLISH", "15m") or ("BEARISH", "15m")
        """
        htf_tf = HTF_TIMEFRAME_MAP.get(tf)
        if not htf_tf:
            return None, None

        cache_key = f"{asset}_{htf_tf}"
        now = time.time()
        cached = self.htf_cache.get(cache_key)
        # Use cache if less than 120 seconds old
        if cached and (now - cached["timestamp"] < 120):
            return cached["bias"], htf_tf

        try:
            df_htf = self.data_loader.fetch_data(asset, timeframe=htf_tf, limit=100, force_download=True)
            df_feat_htf, _ = self.feature_engineer.prepare_features(df_htf, include_target=False)
            if not df_feat_htf.empty:
                latest_htf = df_feat_htf.iloc[-1]
                smc_struct = int(latest_htf.get('smc_structure', 0))
                close = float(latest_htf['close'])
                ema50 = float(latest_htf.get('ema_50', close))

                if smc_struct == 1 and close >= ema50:
                    bias = "BULLISH"
                elif smc_struct == -1 and close <= ema50:
                    bias = "BEARISH"
                elif smc_struct == 1:
                    bias = "BULLISH"
                elif smc_struct == -1:
                    bias = "BEARISH"
                else:
                    bias = "BULLISH" if close >= ema50 else "BEARISH"

                self.htf_cache[cache_key] = {
                    "timestamp": now,
                    "bias": bias,
                    "structure": smc_struct,
                    "close": close,
                    "ema50": ema50
                }
                return bias, htf_tf
        except Exception as e:
            logger.warning(f"Error checking HTF ({htf_tf}) for {asset}: {e}")

        return None, None

    def check_asset(self, asset: str, tf: Optional[str] = None) -> Optional[dict]:
        """
        Executes one monitoring cycle for a given asset and timeframe:
        1. Fetches latest candle
        2. Evaluates HTF (M15 for M5) alignment and generates Trade Setup (min confluence >= 4/6)
        3. Enforces 30-minute Directional Cooldown (blocks flip-flop and duplicate spam)
        4. In paper trading mode, executes step and alerts on SL/TP hits
        """
        tf = tf or self.timeframes[0]
        slug = asset.replace("/", "_").replace(" ", "_").replace("(", "").replace(")", "").lower()
        model_path = MODELS_DIR / f"{slug}_{tf}_model.joblib"

        if not model_path.exists():
            alt_slug = asset.replace("/", "_").replace(" ", "_").lower()
            model_path = MODELS_DIR / f"{alt_slug}_{tf}_model.joblib"

        # 1. Fetch fresh data
        try:
            df_raw = self.data_loader.fetch_data(asset, timeframe=tf, limit=200, force_download=True)
            df_feat, cols = self.feature_engineer.prepare_features(df_raw, include_target=False)
            if df_feat.empty:
                return None
        except Exception as e:
            logger.error(f"Error fetching data for {asset} ({tf}): {e}")
            return None

        # Load or train model
        if model_path.exists():
            model = AITradingModel.load(model_path)
        else:
            logger.info(f"Model for {asset} ({tf}) not found. Training quick baseline model...")
            df_train, train_cols = self.feature_engineer.prepare_features(df_raw, include_target=True)
            model = AITradingModel()
            model.train(df_train, train_cols)
            model.save(model_path)

        latest_candle = df_feat.iloc[-1]
        candle_time = str(df_feat.index[-1])
        current_price = float(latest_candle['close'])

        # 2. Get HTF Bias and Generate Trade Setup (Confluence >= 4/6)
        htf_bias, htf_tf = self.get_htf_bias(asset, tf)
        setup = self.setup_gen.generate_setup(
            asset_name=asset,
            timeframe=tf,
            df_features=df_feat,
            model=model,
            htf_bias=htf_bias,
            htf_timeframe=htf_tf,
            min_confluence=4  # Requirement 2: Confluence >= 4/6
        )

        alert_sent = False
        cache_key = f"{asset}_{tf}"
        now_ts = time.time()
        prev_alert = self.alert_history.get(cache_key)
        cooldown_remaining = 0

        # 3. Check for New Signal Alert with 30-min Directional Cooldown
        if setup.status == "ACTIVE_SETUP":
            if prev_alert:
                elapsed = now_ts - prev_alert["timestamp"]
                prev_dir = prev_alert["direction"]
                rem_sec = int(self.cooldown_seconds - elapsed)

                if elapsed < self.cooldown_seconds:
                    cooldown_remaining = rem_sec
                    # Check if flipping direction (e.g. BUY -> SELL or SELL -> BUY)
                    is_flip = ("BUY" in prev_dir and "SELL" in setup.direction) or ("SELL" in prev_dir and "BUY" in setup.direction)
                    if is_flip:
                        logger.info(
                            f"🚫 [Flip-Flop Prevented] {asset} ({tf}): สลับหน้าเล่นเป็น {setup.direction} "
                            f"ถูกระงับ! อยู่ในระยะ Cooldown 30 นาที (เหลือ {rem_sec//60}m {rem_sec%60}s จากไม้เดิม {prev_dir})"
                        )
                        setup.status = "WAITING"
                        setup.direction = "NEUTRAL (WAIT)"
                        setup.rationale_th = (
                            f"สัญญาณสลับหน้าเล่นเป็น {setup.direction} ถูกระงับโดยระบบ Directional Cooldown 30 นาที "
                            f"(เตือน {prev_dir} ล่าสุดไปเมื่อ {int(elapsed//60)} นาทีก่อน, คงเหลือ cooldown อีก {rem_sec//60}m {rem_sec%60}s)"
                        )
                    else:
                        # Same direction within cooldown -> suppress duplicate alert
                        logger.info(
                            f"⏳ [Cooldown Active] {asset} ({tf}): สัญญาณ {setup.direction} ยังอยู่ในระยะเวลา 30 นาที (เหลือ {rem_sec//60}m {rem_sec%60}s) -> ไม่ส่งเตือนซ้ำ"
                        )
                else:
                    # Cooldown expired -> Broadcast fresh setup!
                    logger.info(f"🔥 NEW {setup.direction} SIGNAL TRIGGERED FOR {asset} ({tf})! (Confluence: {setup.confluence_score}/6)")
                    self.notifier.broadcast_trade_setup(setup)
                    self.alert_history[cache_key] = {
                        "direction": setup.direction,
                        "timestamp": now_ts,
                        "candle_time": candle_time,
                        "price": current_price
                    }
                    self.alerted_candles[cache_key] = candle_time
                    alert_sent = True
            else:
                # First alert for this asset & timeframe
                logger.info(f"🔥 NEW {setup.direction} SIGNAL TRIGGERED FOR {asset} ({tf})! (Confluence: {setup.confluence_score}/6)")
                self.notifier.broadcast_trade_setup(setup)
                self.alert_history[cache_key] = {
                    "direction": setup.direction,
                    "timestamp": now_ts,
                    "candle_time": candle_time,
                    "price": current_price
                }
                self.alerted_candles[cache_key] = candle_time
                alert_sent = True
        elif prev_alert:
            elapsed = now_ts - prev_alert["timestamp"]
            if elapsed < self.cooldown_seconds:
                cooldown_remaining = int(self.cooldown_seconds - elapsed)

        # 4. Optional: Run Paper Trading Step and check for SL/TP execution
        paper_action = "NONE"
        paper_detail = ""
        if self.enable_paper_trade:
            trader = PaperTrader(asset_name=asset, timeframe=tf, model=model)
            step_result = trader.step(
                setup=setup,
                current_price=current_price,
                current_time=candle_time,
                current_high=float(latest_candle['high']),
                current_low=float(latest_candle['low'])
            )
            paper_action = step_result.get("action_taken", "NONE")
            paper_detail = step_result.get("action_detail", "")

            # Alert if position closed (SL or TP) or opened
            if "CLOSED" in paper_action:
                closed_data = step_result.get("closed_trade_data")
                if closed_data:
                    self.notifier.broadcast_position_closed(closed_data)
                else:
                    title = f"📢 Position Closed: {asset} ({tf})"
                    self.notifier.broadcast_text(title, paper_detail)
            elif "OPEN" in paper_action:
                opened_data = step_result.get("opened_trade_data")
                if opened_data:
                    self.notifier.broadcast_position_opened(opened_data, asset=asset, tf=tf)

        report = {
            "timestamp": datetime.now().isoformat(),
            "asset": asset,
            "timeframe": tf,
            "htf": f"{htf_tf}:{htf_bias}" if htf_bias else "N/A",
            "candle_time": candle_time,
            "price": current_price,
            "signal": setup.direction,
            "status": setup.status,
            "confidence": setup.ai_confidence,
            "confluence_score": f"{setup.confluence_score}/{setup.total_confluences}",
            "cooldown_remaining_sec": cooldown_remaining,
            "alert_sent": alert_sent,
            "paper_action": paper_action,
            "paper_detail": paper_detail,
            "setup": {
                "entry": setup.entry_price,
                "sl": setup.stop_loss,
                "tp1": setup.take_profit_1,
                "tp2": setup.take_profit_2,
                "size": setup.recommended_size,
                "candlestick_pattern": setup.candlestick_pattern
            } if setup.status == "ACTIVE_SETUP" else None
        }

        self._record_log(report)
        return report

    def _record_log(self, report: dict):
        """Saves recent monitoring logs"""
        logs = []
        if self.log_file.exists():
            try:
                with open(self.log_file, "r") as f:
                    logs = json.load(f)
            except Exception:
                logs = []

        logs.append(report)
        # Keep last 50 logs
        logs = logs[-50:]

        try:
            with open(self.log_file, "w") as f:
                json.dump(logs, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to write monitor logs: {e}")

    def _update_heartbeat(self, running: Optional[bool] = None):
        """Updates monitor_status.json with current heartbeat timestamp and running state"""
        is_run = self.is_running if running is None else running
        try:
            with open(self.status_file, "w") as f:
                json.dump({
                    "is_running": is_run,
                    "last_heartbeat": datetime.now().isoformat(),
                    "monitored_assets": self.assets,
                    "timeframes": self.timeframes,
                    "interval": self.interval
                }, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to write heartbeat status: {e}")

    def run_single_pass(self) -> List[dict]:
        """Runs one check across all monitored assets and timeframes"""
        results = []
        for asset in self.assets:
            for tf in self.timeframes:
                try:
                    res = self.check_asset(asset, tf)
                    if res:
                        results.append(res)
                except Exception as e:
                    logger.warning(f"Error checking {asset} ({tf}) in single pass: {e}")
        return results

    def start_monitoring_loop(self):
        """Starts 24/7 continuous watcher loop with robust auto-recovery"""
        self.is_running = True
        logger.info(f"🚀 Starting 24/7 Market Monitor for {self.assets} across {self.timeframes} (every {self.interval}s)...")
        self.notifier.broadcast_text(
            "🟢 AI bottrade 24/7 Monitor Started",
            f"ระบบเริ่มติดตามกราฟ {', '.join(self.assets)} ({', '.join(self.timeframes)}) แบบอัตโนมัติแล้ว"
        )
        self._update_heartbeat(running=True)

        cycle_count = 0
        try:
            while self.is_running:
                try:
                    self.load_config()
                    self._update_heartbeat(running=True)

                    for asset in self.assets:
                        for tf in self.timeframes:
                            try:
                                res = self.check_asset(asset, tf)
                                if res:
                                    t = res['timestamp'].split('T')[1][:8]
                                    p = res['price']
                                    sig = res['signal']
                                    conf = res['confidence']
                                    score = res.get('confluence_score', '0/6')
                                    htf_s = res.get('htf', 'N/A')
                                    cd_rem = res.get('cooldown_remaining_sec', 0)
                                    cd_s = f"CD:{cd_rem//60}m" if cd_rem > 0 else "Ready"
                                    p_str = format_currency_price(asset, p)
                                    print(f"[{t}] {asset:<18} ({tf:<3}) | Price: {p_str:<12} | HTF: {htf_s:<14} | Signal: {sig:<14} ({conf:.1%}) | SMC: {score:<3} | {cd_s}")
                            except Exception as asset_err:
                                logger.warning(f"Error checking {asset} ({tf}): {asset_err}")

                    cycle_count += 1
                    # Heartbeat notification every 6 hours (e.g. 360 cycles at 60s)
                    hb_cycles = int(6 * 3600 / max(self.interval, 10))
                    if cycle_count > 0 and cycle_count % hb_cycles == 0:
                        self.notifier.broadcast_text(
                            "💓 AI bottrade Monitor Heartbeat",
                            f"บอททำงานปกติ 24/7 | สแกนต่อเนื่อง {cycle_count} รอบ\nสินทรัพย์: {', '.join(self.assets)} ({', '.join(self.timeframes)})"
                        )

                except Exception as loop_err:
                    logger.error(f"Unexpected error in monitor loop: {loop_err}", exc_info=True)

                time.sleep(self.interval)
        except KeyboardInterrupt:
            self.is_running = False
            self._update_heartbeat(running=False)
            logger.info("Monitor loop stopped by user.")
            self.notifier.broadcast_text("🛑 AI bottrade Monitor Stopped", "ระบบหยุดการติดตามกราฟแล้ว")
