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

from src.config import DATA_DIR, MODELS_DIR, SUPPORTED_ASSETS, TradingConfig
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

        self.data_loader = MarketDataLoader()
        self.feature_engineer = FeatureEngineer()
        self.notifier = AlertNotifier()
        self.setup_gen = TradeSetupGenerator()

        self.log_file = DATA_DIR / "monitor_activity.json"
        self.status_file = DATA_DIR / "monitor_status.json"

        # Cooldown cache: (asset_tf) -> candle_time
        self.alerted_candles: Dict[str, str] = {}
        self.is_running = False

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
            with open(self.status_file, "w") as f:
                json.dump({
                    "is_running": self.is_running,
                    "last_heartbeat": datetime.now().isoformat(),
                    "monitored_assets": self.assets,
                    "timeframes": self.timeframes
                }, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to write monitor logs: {e}")

    def run_single_pass(self) -> List[dict]:
        """Runs one check across all monitored assets and timeframes"""
        results = []
        for asset in self.assets:
            for tf in self.timeframes:
                res = self.check_asset(asset, tf)
                if res:
                    results.append(res)
        return results

    def start_monitoring_loop(self):
        """Starts 24/7 continuous watcher loop"""
        self.is_running = True
        logger.info(f"🚀 Starting 24/7 Market Monitor for {self.assets} across {self.timeframes} (every {self.interval}s)...")
        self.notifier.broadcast_text(
            "🟢 AI bottrade 24/7 Monitor Started",
            f"ระบบเริ่มติดตามกราฟ {', '.join(self.assets)} ({', '.join(self.timeframes)}) แบบอัตโนมัติแล้ว"
        )

        try:
            while self.is_running:
                for asset in self.assets:
                    for tf in self.timeframes:
                        res = self.check_asset(asset, tf)
                        if res:
                            t = res['timestamp'].split('T')[1][:8]
                            p = res['price']
                            sig = res['signal']
                            conf = res['confidence']
                            print(f"[{t}] {asset:<18} ({tf:<3}) | Price: ${p:,.2f} | Signal: {sig:<14} ({conf:.1%})")
                time.sleep(self.interval)
        except KeyboardInterrupt:
            self.is_running = False
            logger.info("Monitor loop stopped by user.")
            self.notifier.broadcast_text("🛑 AI bottrade Monitor Stopped", "ระบบหยุดการติดตามกราฟแล้ว")
