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

from src.config import DATA_DIR, TradingConfig, SUPPORTED_ASSETS
from src.data_loader import MarketDataLoader
from src.feature_engineering import FeatureEngineer
from src.model import AITradingModel
from src.continuous_learning import ContinuousLearner

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
            "last_updated": datetime.now().isoformat()
        }
        with open(self.state_file, "w") as f:
            json.dump(state, f, indent=2)

    def reset_portfolio(self):
        """Reset balance to initial balance and clear open positions"""
        self.cash = self.config.initial_balance
        self.open_position = None
        self.trade_history = []
        self.save_state()

    def step(self) -> dict:
        """
        Execute one evaluation step:
        1. Fetch fresh market data
        2. Evaluate active position for SL / TP
        3. Run AI prediction if flat
        4. Execute action and save state
        """
        if self.model is None or not self.model.is_trained:
            return {"status": "error", "message": "Model is not loaded or trained."}

        # 1. Fetch fresh data (bypass cache to get latest candle)
        df_raw = self.data_loader.fetch_data(
            asset_name=self.asset_name,
            timeframe=self.timeframe,
            limit=300,
            force_download=True
        )

        # 2. Extract features
        df_feat, feature_cols = self.feature_engineer.prepare_features(df_raw, include_target=False)
        if len(df_feat) == 0:
            return {"status": "error", "message": "Not enough data to calculate indicators."}

        latest_bar = df_feat.iloc[-1]
        current_time = str(df_feat.index[-1])
        current_price = float(latest_bar['close'])
        current_atr = float(latest_bar['atr']) if 'atr' in latest_bar else current_price * 0.01

        asset_info = SUPPORTED_ASSETS.get(self.asset_name, {})
        fee_rate = asset_info.get("fee_rate", 0.00075)

        action_taken = "NONE"
        action_detail = ""

        # 3. Check Open Position for Exit
        if self.open_position is not None:
            pos = self.open_position
            entry_price = pos['entry_price']
            size = pos['size']
            sl_price = pos['sl_price']
            tp_price = pos['tp_price']

            hit_sl = current_price <= sl_price
            hit_tp = current_price >= tp_price

            exit_reason = None
            if hit_sl:
                exit_reason = "STOP_LOSS"
            elif hit_tp:
                exit_reason = "TAKE_PROFIT"

            if exit_reason:
                exit_fee = current_price * size * fee_rate
                gross_pnl = (current_price - entry_price) * size
                net_pnl = gross_pnl - pos.get('entry_fee', 0.0) - exit_fee
                self.cash += (current_price * size) - exit_fee

                closed_trade = {
                    "entry_time": pos['entry_time'],
                    "exit_time": current_time,
                    "entry_price": entry_price,
                    "exit_price": current_price,
                    "size": size,
                    "net_pnl": round(net_pnl, 2),
                    "net_pnl_pct": round((net_pnl / (entry_price * size)) * 100, 2),
                    "exit_reason": exit_reason,
                    "fee_paid": round(pos.get('entry_fee', 0.0) + exit_fee, 4)
                }
                self.trade_history.append(closed_trade)

                # Feed outcome into Continuous Learning Experience Buffer
                self.continuous_learner.record_experience(
                    entry_time=pos['entry_time'],
                    exit_time=current_time,
                    entry_price=entry_price,
                    exit_price=current_price,
                    pnl=net_pnl,
                    pnl_pct=closed_trade['net_pnl_pct'],
                    exit_reason=exit_reason,
                    confidence_at_entry=pos.get('confidence', 0.55),
                    smc_structure=pos.get('smc_structure', 1),
                    range_position=pos.get('range_position', 0.5)
                )

                self.open_position = None
                action_taken = f"CLOSED_{exit_reason}"
                action_detail = f"Closed at ${current_price:.2f} | Net PnL: ${net_pnl:.2f} ({closed_trade['net_pnl_pct']}%)"
                self.save_state()

        # 4. If flat, check AI Signal with self-adaptive threshold
        self.model.confidence_threshold = self.continuous_learner.get_adaptive_confidence_threshold()
        signal, confidence, prob_dict = self.model.predict_signal(latest_bar)

        if self.open_position is None and signal == 1:
            # Sizing based on risk
            risk_amount = self.cash * self.config.risk_per_trade
            atr_distance = max(current_atr * self.config.sl_atr_multiplier, current_price * 0.005)
            size = risk_amount / atr_distance

            # Cap size by available cash
            max_size = (self.cash * 0.95) / current_price
            if size > max_size:
                size = max_size

            order_value = size * current_price
            if order_value >= 15.0: # Minimum order value
                entry_fee = order_value * fee_rate
                self.cash -= (order_value + entry_fee)

                sl_price = current_price - (self.config.sl_atr_multiplier * current_atr)
                tp_price = current_price + (self.config.tp_atr_multiplier * current_atr)

                self.open_position = {
                    "entry_time": current_time,
                    "entry_price": current_price,
                    "size": size,
                    "sl_price": round(sl_price, 4),
                    "tp_price": round(tp_price, 4),
                    "entry_fee": entry_fee,
                    "order_value": order_value,
                    "confidence": round(confidence, 4),
                    "smc_structure": int(latest_bar.get('smc_structure', 1)),
                    "range_position": float(latest_bar.get('range_position', 0.5))
                }
                action_taken = "OPEN_LONG"
                action_detail = f"Bought {size:.4f} units at ${current_price:.2f} (SL: ${sl_price:.2f}, TP: ${tp_price:.2f}, Conf: {confidence:.1%})"
                self.save_state()

        # Calculate current total portfolio equity
        unrealized_pnl = 0.0
        pos_value = 0.0
        if self.open_position is not None:
            pos_value = self.open_position['size'] * current_price
            unrealized_pnl = (current_price - self.open_position['entry_price']) * self.open_position['size']

        total_equity = self.cash + pos_value

        return {
            "status": "success",
            "timestamp": current_time,
            "asset": self.asset_name,
            "price": current_price,
            "ai_signal": "BUY" if signal == 1 else ("SELL" if signal == -1 else "HOLD"),
            "confidence": round(confidence, 4),
            "adaptive_confidence_threshold": self.continuous_learner.get_adaptive_confidence_threshold(),
            "probabilities": {k: round(v, 4) for k, v in prob_dict.items()},
            "action_taken": action_taken,
            "action_detail": action_detail,
            "cash": round(self.cash, 2),
            "position_value": round(pos_value, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "total_equity": round(total_equity, 2),
            "has_open_position": self.open_position is not None,
            "open_position": self.open_position,
            "total_closed_trades": len(self.trade_history),
            "learning_experiences": len(self.continuous_learner.experiences)
        }
