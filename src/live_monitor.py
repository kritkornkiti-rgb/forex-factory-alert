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
from typing import Dict, List, Optional
import pandas as pd

from src.config import DATA_DIR, MODELS_DIR, SUPPORTED_ASSETS, TradingConfig, format_currency_price
from src.data_loader import MarketDataLoader
from src.feature_engineering import FeatureEngineer
from src.model import AITradingModel
from src.notifier import AlertNotifier
from src.paper_trader import PaperTrader
from src.trade_setup import TradeSetup, TradeSetupGenerator

logger = logging.getLogger("AI-bottrade-monitor")


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

    def check_asset(self, asset: str, tf: Optional[str] = None) -> Optional[dict]:
        """
        Executes one monitoring cycle for a given asset and timeframe:
        1. Fetches latest candle
        2. Runs SMC & AI
        3. Checks if new trade setup triggered (and broadcasts alert)
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

        # 2. Generate Trade Setup
        setup = self.setup_gen.generate_setup(
            asset_name=asset,
            timeframe=tf,
            df_features=df_feat,
            model=model
        )

        alert_sent = False
        cache_key = f"{asset}_{tf}"
        # 3. Check for New Signal Alert
        if setup.status == "ACTIVE_SETUP":
            last_alerted = self.alerted_candles.get(cache_key)
            if last_alerted != candle_time:
                logger.info(f"🔥 NEW {setup.direction} SIGNAL TRIGGERED FOR {asset} ({tf})!")
                self.notifier.broadcast_trade_setup(setup)
                self.alerted_candles[cache_key] = candle_time
                alert_sent = True

        # 4. Optional: Run Paper Trading Step and check for SL/TP execution
        paper_action = "NONE"
        paper_detail = ""
        if self.enable_paper_trade:
            trader = PaperTrader(asset_name=asset, timeframe=tf, model=model)
            step_result = trader.step()
            paper_action = step_result.get("action_taken", "NONE")
            paper_detail = step_result.get("action_detail", "")

            # Alert if position closed (SL or TP)
            if "CLOSED" in paper_action:
                title = f"📢 Position Closed: {asset} ({tf})"
                self.notifier.broadcast_text(title, paper_detail)

        report = {
            "timestamp": datetime.now().isoformat(),
            "asset": asset,
            "timeframe": tf,
            "candle_time": candle_time,
            "price": current_price,
            "signal": setup.direction,
            "status": setup.status,
            "confidence": setup.ai_confidence,
            "confluence_score": f"{setup.confluence_score}/{setup.total_confluences}",
            "alert_sent": alert_sent,
            "paper_action": paper_action,
            "paper_detail": paper_detail,
            "setup": {
                "entry": setup.entry_price,
                "sl": setup.stop_loss,
                "tp1": setup.take_profit_1,
                "tp2": setup.take_profit_2,
                "size": setup.recommended_size
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
                                    p_str = format_currency_price(asset, p)
                                    print(f"[{t}] {asset:<18} ({tf:<3}) | Price: {p_str:<12} | Signal: {sig:<14} ({conf:.1%}) | SMC: {score}")
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
