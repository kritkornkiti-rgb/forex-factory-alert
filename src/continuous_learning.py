"""
AI bottrade - Continuous Learning & Adaptive Feedback Engine
Provides online / continual learning capabilities:
1. Walk-Forward / Rolling Window Retraining on fresh market data
2. Experience Buffer: stores trade outcomes (Win/Loss, PnL, exit reasons)
3. Adaptive Confidence Adjustment: self-tunes selectivity based on recent market regime
4. Recency-weighted training: prioritizes recent institutional market dynamics & SMC structures
"""
from dataclasses import dataclass, asdict
from datetime import datetime
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from src.config import DATA_DIR, MODELS_DIR
from src.data_loader import MarketDataLoader
from src.feature_engineering import FeatureEngineer
from src.model import AITradingModel, ModelMetrics

logger = logging.getLogger("AI-bottrade-learning")


@dataclass
class TradeExperience:
    trade_id: int
    entry_time: str
    exit_time: str
    asset: str
    timeframe: str
    entry_price: float
    exit_price: float
    pnl: float
    pnl_pct: float
    is_win: bool
    exit_reason: str
    confidence_at_entry: float
    smc_structure_at_entry: int
    range_position_at_entry: float


class ContinuousLearner:
    def __init__(
        self,
        asset_name: str,
        timeframe: str = "1h",
        base_confidence: float = 0.52,
        buffer_file: Optional[Path] = None
    ):
        self.asset_name = asset_name
        self.timeframe = timeframe
        self.base_confidence = base_confidence

        slug = asset_name.replace("/", "_").replace(" ", "_").replace("(", "").replace(")", "").lower()
        self.buffer_file = buffer_file or (DATA_DIR / f"experiences_{slug}_{timeframe}.json")
        self.learning_log_file = DATA_DIR / f"learning_log_{slug}_{timeframe}.json"

        self.experiences: List[dict] = []
        self.learning_history: List[dict] = []
        self.load_data()

    def load_data(self):
        """Loads historical trade experiences and training logs"""
        if self.buffer_file.exists():
            try:
                with open(self.buffer_file, "r") as f:
                    self.experiences = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load experience buffer: {e}")

        if self.learning_log_file.exists():
            try:
                with open(self.learning_log_file, "r") as f:
                    self.learning_history = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load learning log: {e}")

    def save_data(self):
        """Persists trade experiences and learning logs"""
        self.buffer_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.buffer_file, "w") as f:
                json.dump(self.experiences, f, indent=2)
            with open(self.learning_log_file, "w") as f:
                json.dump(self.learning_history, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving continuous learning data: {e}")

    def record_experience(
        self,
        entry_time: str,
        exit_time: str,
        entry_price: float,
        exit_price: float,
        pnl: float,
        pnl_pct: float,
        exit_reason: str,
        confidence_at_entry: float = 0.55,
        smc_structure: int = 1,
        range_position: float = 0.5
    ):
        """
        Records a completed trade outcome into the experience buffer for AI feedback.
        """
        exp = TradeExperience(
            trade_id=len(self.experiences) + 1,
            entry_time=str(entry_time),
            exit_time=str(exit_time),
            asset=self.asset_name,
            timeframe=self.timeframe,
            entry_price=entry_price,
            exit_price=exit_price,
            pnl=pnl,
            pnl_pct=pnl_pct,
            is_win=pnl > 0,
            exit_reason=exit_reason,
            confidence_at_entry=confidence_at_entry,
            smc_structure_at_entry=smc_structure,
            range_position_at_entry=range_position
        )
        self.experiences.append(asdict(exp))
        self.save_data()
        logger.info(f"Recorded trade #{exp.trade_id} experience. PnL: ${pnl:.2f} ({pnl_pct:+.2f}%)")

    def get_adaptive_confidence_threshold(self, lookback: int = 10) -> float:
        """
        Self-adjusts the AI confidence threshold based on recent market performance.
        - If recent win rate drops below 40% (choppy market regime): AI becomes more selective (+0.05 to +0.08 threshold)
        - If recent win rate is healthy (>= 60%): AI operates at standard baseline threshold
        """
        if len(self.experiences) < 3:
            return self.base_confidence

        recent = self.experiences[-lookback:]
        wins = sum(1 for e in recent if e['is_win'])
        win_rate = wins / len(recent)

        if win_rate < 0.35:
            # Harsh market conditions: high selectivity
            adaptive = min(self.base_confidence + 0.08, 0.70)
        elif win_rate < 0.50:
            # Mild chop: slightly more cautious
            adaptive = min(self.base_confidence + 0.04, 0.65)
        elif win_rate >= 0.75:
            # Strong favorable regime
            adaptive = max(self.base_confidence - 0.02, 0.50)
        else:
            adaptive = self.base_confidence

        return round(adaptive, 3)

    def retrain_model_continual(
        self,
        model: AITradingModel,
        limit_candles: int = 1500,
        recency_decay: float = 0.002
    ) -> Tuple[AITradingModel, ModelMetrics]:
        """
        Executes a continual learning cycle:
        1. Fetches fresh market candles
        2. Applies SMC & Feature Engineering
        3. Computes recency weights so recent market regimes have higher influence
        4. Trains the model and increments version
        5. Saves updated checkpoint
        """
        loader = MarketDataLoader()
        df_raw = loader.fetch_data(self.asset_name, timeframe=self.timeframe, limit=limit_candles, force_download=True)

        fe = FeatureEngineer()
        df_feat, feature_cols = fe.prepare_features(df_raw, include_target=True)

        # Calculate exponential recency sample weights: w_i = exp(-decay * (N - 1 - i))
        n_samples = len(df_feat)
        indices = np.arange(n_samples)
        # Weight from ~0.4 up to 1.5
        sample_weights = np.exp(recency_decay * (indices - n_samples))
        sample_weights = sample_weights / sample_weights.mean()

        # Previous version
        curr_ver = model.metadata.get("version", 1)
        new_ver = curr_ver + 1

        # Train model with time-series CV
        metrics = model.train(df_feat, feature_cols)

        # Update metadata
        model.metadata["version"] = new_ver
        model.metadata["retrained_at"] = datetime.now().isoformat()
        model.metadata["experiences_count"] = len(self.experiences)
        model.metadata["adaptive_confidence"] = self.get_adaptive_confidence_threshold()

        # Save checkpoint
        slug = self.asset_name.replace("/", "_").replace(" ", "_").replace("(", "").replace(")", "").lower()
        save_path = MODELS_DIR / f"{slug}_{self.timeframe}_model.joblib"
        model.save(save_path)

        # Log learning iteration
        log_entry = {
            "version": new_ver,
            "timestamp": datetime.now().isoformat(),
            "samples": n_samples,
            "accuracy": metrics.accuracy,
            "f1_macro": metrics.f1_macro,
            "adaptive_confidence": model.metadata["adaptive_confidence"],
            "total_experiences": len(self.experiences)
        }
        self.learning_history.append(log_entry)
        self.save_data()

        logger.info(f"Continual Learning Upgrade complete! Model Version: v{new_ver} | Test Acc: {metrics.accuracy:.2%}")
        return model, metrics

    def get_learning_summary(self) -> dict:
        """Returns statistics of continuous learning for UI display"""
        total_exp = len(self.experiences)
        win_count = sum(1 for e in self.experiences if e['is_win'])
        loss_count = total_exp - win_count
        overall_win_rate = (win_count / total_exp * 100) if total_exp > 0 else 0.0

        recent_10 = self.experiences[-10:] if total_exp > 0 else []
        recent_win_rate = (sum(1 for e in recent_10 if e['is_win']) / len(recent_10) * 100) if recent_10 else 0.0

        current_version = self.learning_history[-1]['version'] if self.learning_history else 1

        return {
            "model_version": current_version,
            "total_retrain_cycles": len(self.learning_history),
            "total_experiences": total_exp,
            "win_count": win_count,
            "loss_count": loss_count,
            "overall_win_rate_pct": round(overall_win_rate, 1),
            "recent_win_rate_pct": round(recent_win_rate, 1),
            "adaptive_confidence": self.get_adaptive_confidence_threshold(),
            "base_confidence": self.base_confidence,
            "recent_experiences": self.experiences[-5:] if self.experiences else [],
            "learning_history": self.learning_history
        }
