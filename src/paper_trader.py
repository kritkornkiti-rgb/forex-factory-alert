"""
AI bottrade - Real-time Paper Trading Engine
Simulates live order execution with virtual portfolio balance, dynamic SL/TP checks,
and persistent trade logging without risking real capital.
"""
from dataclasses import dataclass, asdict
from datetime import datetime
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd

from src.config import DATA_DIR, TradingConfig, SUPPORTED_ASSETS, format_currency_price
from src.data_loader import MarketDataLoader
from src.feature_engineering import FeatureEngineer
from src.model import AITradingModel
from src.continuous_learning import ContinuousLearner
from src.trade_setup import TradeSetup, TradeSetupGenerator

logger = logging.getLogger("AI-bottrade-paper")


class PaperTrader:
    def __init__(
        self,
        asset_name: str,
        timeframe: str = "1h",
        model: Optional[AITradingModel] = None,
        config: Optional[TradingConfig] = None,
        state_file: Optional[Path] = None
    ):
        self.asset_name = asset_name
        self.timeframe = timeframe
        self.model = model
        self.config = config or TradingConfig()
        self.data_loader = MarketDataLoader()
        self.feature_engineer = FeatureEngineer()
        self.trade_setup_gen = TradeSetupGenerator(config=self.config)
        self.continuous_learner = ContinuousLearner(
            asset_name=asset_name,
            timeframe=timeframe,
            base_confidence=self.config.confidence_threshold
        )

        slug = asset_name.replace("/", "_").replace(" ", "_").lower()
        self.state_file = state_file or (DATA_DIR / f"paper_state_{slug}_{timeframe}.json")

        self.cash: float = self.config.initial_balance
        self.open_position: Optional[dict] = None
        self.trade_history: List[dict] = []
        self.last_sl_timestamp: float = 0.0
        self.last_sl_direction: Optional[str] = None
        self.load_state()

    def load_state(self):
        """Load persistent portfolio state from disk"""
        if self.state_file.exists():
            try:
                with open(self.state_file, "r") as f:
                    state = json.load(f)
                    self.cash = state.get("cash", self.config.initial_balance)
                    self.open_position = state.get("open_position")
                    self.trade_history = state.get("trade_history", [])
                    self.last_sl_timestamp = float(state.get("last_sl_timestamp", 0.0))
                    self.last_sl_direction = state.get("last_sl_direction", None)
                    logger.info(f"Loaded paper trade state. Cash: ${self.cash:.2f}")
            except Exception as e:
                logger.error(f"Error loading state: {e}. Using clean state.")

    def save_state(self):
        """Save persistent portfolio state to disk"""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        state = {
            "asset_name": self.asset_name,
            "timeframe": self.timeframe,
            "cash": self.cash,
            "open_position": self.open_position,
            "trade_history": self.trade_history,
            "last_sl_timestamp": self.last_sl_timestamp,
            "last_sl_direction": self.last_sl_direction,
            "last_updated": datetime.now().isoformat()
        }
        with open(self.state_file, "w") as f:
            json.dump(state, f, indent=2)

    def reset_portfolio(self):
        """Reset balance to initial balance and clear open positions"""
        self.cash = self.config.initial_balance
        self.open_position = None
        self.trade_history = []
        self.last_sl_timestamp = 0.0
        self.last_sl_direction = None
        self.save_state()

    def step(
        self,
        setup: Optional[TradeSetup] = None,
        current_price: Optional[float] = None,
        current_time: Optional[str] = None,
        current_high: Optional[float] = None,
        current_low: Optional[float] = None
    ) -> dict:
        """
        Execute one evaluation step:
        1. Evaluate active position for SL / TP exits (using high/low price wicks)
        2. If closed on this step, record experience, save state, and stay flat (no immediate re-entry)
        3. If flat, check for 30-minute SL Cooldown (prevent revenge trading / consecutive loss streaks)
        4. If flat and confirmed setup exists (status == "ACTIVE_SETUP"):
           Open position matching the exact setup levels (entry, SL, TP, size)
        5. Return step execution report
        """
        if setup is None and (self.model is None or not self.model.is_trained):
            return {"status": "error", "message": "Model is not loaded or trained."}

        # 1. If market data not passed in, fetch fresh data and generate features
        if current_price is None or setup is None:
            df_raw = self.data_loader.fetch_data(
                asset_name=self.asset_name,
                timeframe=self.timeframe,
                limit=300,
                force_download=True
            )
            df_feat, feature_cols = self.feature_engineer.prepare_features(df_raw, include_target=False)
            if len(df_feat) == 0:
                return {"status": "error", "message": "Not enough data to calculate indicators."}

            latest_bar = df_feat.iloc[-1]
            if current_time is None:
                current_time = str(df_feat.index[-1])
            if current_price is None:
                current_price = float(latest_bar['close'])
            if current_high is None:
                current_high = float(latest_bar['high'])
            if current_low is None:
                current_low = float(latest_bar['low'])

            if setup is None:
                setup = self.trade_setup_gen.generate_setup(
                    asset_name=self.asset_name,
                    timeframe=self.timeframe,
                    df_features=df_feat,
                    model=self.model,
                    capital=self.cash,
                    risk_pct=self.config.risk_per_trade,
                    min_confluence=4
                )
        else:
            if current_high is None:
                current_high = current_price
            if current_low is None:
                current_low = current_price
            if current_time is None:
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M")

        asset_info = SUPPORTED_ASSETS.get(self.asset_name, {})
        fee_rate = asset_info.get("fee_rate", 0.00075)

        action_taken = "NONE"
        action_detail = ""
        closed_trade_data = None
        opened_trade_data = None

        # 2. Check Active Position for Exit (SL or TP)
        if self.open_position is not None:
            pos = self.open_position
            direction = pos.get('direction', 'BUY (LONG)')
            is_long = "BUY" in direction.upper() or "LONG" in direction.upper()
            entry_price = float(pos['entry_price'])
            size = float(pos['size'])
            sl_price = float(pos['sl_price'])
            tp_price = float(pos['tp_price'])

            hit_sl = False
            hit_tp = False
            exec_price = current_price

            if is_long:
                if current_low <= sl_price or current_price <= sl_price:
                    hit_sl = True
                    exec_price = sl_price
                elif current_high >= tp_price or current_price >= tp_price:
                    hit_tp = True
                    exec_price = tp_price
                gross_pnl = (exec_price - entry_price) * size
            else:
                if current_high >= sl_price or current_price >= sl_price:
                    hit_sl = True
                    exec_price = sl_price
                elif current_low <= tp_price or current_price <= tp_price:
                    hit_tp = True
                    exec_price = tp_price
                gross_pnl = (entry_price - exec_price) * size

            exit_reason = None
            if hit_sl:
                exit_reason = "STOP_LOSS"
                self.last_sl_timestamp = datetime.now().timestamp()
                self.last_sl_direction = direction
            elif hit_tp:
                exit_reason = "TAKE_PROFIT"

            if exit_reason:
                exit_fee = exec_price * size * fee_rate
                net_pnl = gross_pnl - pos.get('entry_fee', 0.0) - exit_fee
                if is_long:
                    self.cash += (exec_price * size) - exit_fee
                else:
                    self.cash += (entry_price * size) + net_pnl

                # Calculate holding duration
                try:
                    t_entry = pd.to_datetime(pos['entry_time'])
                    t_exit = pd.to_datetime(current_time)
                    total_sec = max(0, int((t_exit - t_entry).total_seconds()))
                    hrs = total_sec // 3600
                    mins = (total_sec % 3600) // 60
                    duration_str = f"{hrs} ชม. {mins} นาที" if hrs > 0 else f"{mins} นาที"
                except Exception:
                    duration_str = "N/A"

                closed_trade = {
                    "asset": self.asset_name,
                    "timeframe": self.timeframe,
                    "direction": direction,
                    "entry_time": pos['entry_time'],
                    "exit_time": current_time,
                    "entry_price": entry_price,
                    "exit_price": exec_price,
                    "size": size,
                    "duration_str": duration_str,
                    "net_pnl": round(net_pnl, 2),
                    "net_pnl_pct": round((net_pnl / (entry_price * size + 1e-10)) * 100, 2),
                    "exit_reason": exit_reason,
                    "fee_paid": round(pos.get('entry_fee', 0.0) + exit_fee, 4)
                }
                self.trade_history.append(closed_trade)
                closed_trade_data = closed_trade

                # Feed outcome into Continuous Learning Experience Buffer
                self.continuous_learner.record_experience(
                    entry_time=pos['entry_time'],
                    exit_time=current_time,
                    entry_price=entry_price,
                    exit_price=exec_price,
                    pnl=net_pnl,
                    pnl_pct=closed_trade['net_pnl_pct'],
                    exit_reason=exit_reason,
                    confidence_at_entry=pos.get('confidence', 0.55),
                    smc_structure=pos.get('smc_structure', 1),
                    range_position=pos.get('range_position', 0.5)
                )

                self.open_position = None
                action_taken = f"CLOSED_{exit_reason}"
                p_c_str = format_currency_price(self.asset_name, exec_price)
                action_detail = f"Closed {direction} at {p_c_str} ({duration_str}) | Net PnL: ${net_pnl:.2f} ({closed_trade['net_pnl_pct']}%) | Reason: {exit_reason}"
                self.save_state()

        # 3. If flat (and not just closed on this step), check for Setup Entry
        if self.open_position is None and not action_taken.startswith("CLOSED"):
            if setup is None:
                action_taken = "NONE"
                action_detail = "Flat. Waiting for setup."
            elif setup.status != "ACTIVE_SETUP":
                action_taken = "NONE"
                action_detail = f"Flat. {setup.sl_reason}"
            else:
                # Setup is ACTIVE_SETUP! Check 30-minute SL Cooldown to prevent streak losses
                now_ts = datetime.now().timestamp()
                is_sl_cooldown = False
                if self.last_sl_direction and (
                    ("BUY" in setup.direction and "BUY" in self.last_sl_direction) or
                    ("SELL" in setup.direction and "SELL" in self.last_sl_direction)
                ):
                    elapsed_sl = now_ts - self.last_sl_timestamp
                    if elapsed_sl < 1800:
                        is_sl_cooldown = True
                        rem_m = int((1800 - elapsed_sl) // 60)
                        rem_s = int((1800 - elapsed_sl) % 60)
                        action_taken = "SL_COOLDOWN"
                        action_detail = f"ชะลอการเปิดสถานะ {setup.direction} ซ้ำหลังเพิ่งชน Stop Loss (เหลือระยะพัก {rem_m} นาที {rem_s} วินาที เพื่อป้องกัน Revenge Trading)"
                        logger.info(f"⏳ [PaperTrader SL Cooldown] {self.asset_name}: {action_detail}")

                if not is_sl_cooldown:
                    entry_p = setup.entry_price
                    size = setup.recommended_size
                    max_size = (self.cash * 0.95) / (entry_p if entry_p > 0 else 1.0)
                    if size > max_size:
                        size = max_size

                    order_value = size * entry_p
                    if order_value >= 10.0:
                        entry_fee = order_value * fee_rate
                        self.cash -= (order_value + entry_fee)

                        if "BUY" in setup.direction:
                            pos_dir = "BUY (LONG)"
                            action_taken = "OPEN_LONG"
                        else:
                            pos_dir = "SELL (SHORT)"
                            action_taken = "OPEN_SHORT"

                        self.open_position = {
                            "direction": pos_dir,
                            "entry_time": current_time,
                            "entry_price": entry_p,
                            "size": size,
                            "sl_price": setup.stop_loss,
                            "tp_price": setup.take_profit_1,
                            "tp2_price": setup.take_profit_2,
                            "entry_fee": entry_fee,
                            "order_value": order_value,
                            "confidence": setup.ai_confidence,
                            "confluence_score": setup.confluence_score,
                            "candlestick_pattern": setup.candlestick_pattern,
                            "rationale": setup.rationale_th
                        }
                        opened_trade_data = self.open_position
                        p_c_str = format_currency_price(self.asset_name, entry_p)
                        action_detail = (
                            f"{pos_dir} {size:.4f} units at {p_c_str} "
                            f"(Entry Time: {current_time}, Conf: {setup.ai_confidence:.1%}, "
                            f"Confluence: {setup.confluence_score}/{setup.total_confluences})"
                        )
                        self.save_state()

        # Calculate current total portfolio equity
        unrealized_pnl = 0.0
        pos_value = 0.0
        if self.open_position is not None:
            pos_value = self.open_position['size'] * current_price
            pos_dir = self.open_position.get('direction', 'BUY')
            if "BUY" in pos_dir or "LONG" in pos_dir:
                unrealized_pnl = (current_price - self.open_position['entry_price']) * self.open_position['size']
                total_equity = self.cash + pos_value
            else:
                unrealized_pnl = (self.open_position['entry_price'] - current_price) * self.open_position['size']
                total_equity = self.cash + self.open_position.get('order_value', pos_value) + unrealized_pnl
        else:
            total_equity = self.cash

        return {
            "status": "success",
            "timestamp": current_time,
            "asset": self.asset_name,
            "price": current_price,
            "ai_signal": setup.direction if setup else "HOLD",
            "confidence": setup.ai_confidence if setup else 0.0,
            "adaptive_confidence_threshold": self.continuous_learner.get_adaptive_confidence_threshold(),
            "action_taken": action_taken,
            "action_detail": action_detail,
            "closed_trade_data": closed_trade_data,
            "opened_trade_data": opened_trade_data,
            "cash": round(self.cash, 2),
            "position_value": round(pos_value, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "total_equity": round(total_equity, 2),
            "has_open_position": self.open_position is not None,
            "open_position": self.open_position,
            "total_closed_trades": len(self.trade_history),
            "learning_experiences": len(self.continuous_learner.experiences)
        }

