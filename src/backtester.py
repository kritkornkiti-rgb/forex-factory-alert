"""
AI bottrade - Realistic Backtesting Engine
Simulates order execution with realistic slippage, maker/taker exchange fees,
ATR-based dynamic Stop-Loss & Take-Profit, and portfolio risk management.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
import numpy as np
import pandas as pd

from src.config import TradingConfig


@dataclass
class TradeRecord:
    entry_time: pd.Timestamp
    exit_time: Optional[pd.Timestamp] = None
    entry_price: float = 0.0
    exit_price: float = 0.0
    size: float = 0.0
    side: str = "LONG"
    pnl: float = 0.0
    pnl_pct: float = 0.0
    fee_paid: float = 0.0
    exit_reason: str = "" # "TAKE_PROFIT", "STOP_LOSS", "SIGNAL_EXIT", "END_OF_DATA"
    duration_bars: int = 0


@dataclass
class BacktestResult:
    initial_balance: float
    final_balance: float
    total_return_pct: float
    buy_hold_return_pct: float
    max_drawdown_pct: float
    sharpe_ratio: float
    profit_factor: float
    win_rate_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    equity_curve: pd.DataFrame
    trades_df: pd.DataFrame


class BacktestEngine:
    def __init__(
        self,
        config: TradingConfig = None,
        fee_rate: float = 0.00075, # 0.075%
        slippage: float = 0.0002   # 0.02%
    ):
        self.config = config or TradingConfig()
        self.fee_rate = fee_rate
        self.slippage = slippage

    def run(
        self,
        df: pd.DataFrame,
        signals: np.ndarray,
        confidences: np.ndarray
    ) -> BacktestResult:
        """
        Executes chronological simulation over the DataFrame bars.
        df must have: 'open', 'high', 'low', 'close', 'atr'
        """
        df = df.copy()
        n = len(df)
        if n == 0 or len(signals) != n:
            raise ValueError("Data and signals length must match and be non-empty.")

        cash = self.config.initial_balance
        equity_records = []
        trades: List[TradeRecord] = []
        active_trade: Optional[TradeRecord] = None
        entry_idx = 0
        sl_price = 0.0
        tp_price = 0.0

        close_prices = df['close'].values
        high_prices = df['high'].values
        low_prices = df['low'].values
        open_prices = df['open'].values
        atr_values = df['atr'].values
        timestamps = df.index

        for i in range(n):
            current_time = timestamps[i]
            current_close = close_prices[i]
            current_high = high_prices[i]
            current_low = low_prices[i]
            current_open = open_prices[i]
            current_atr = atr_values[i] if not np.isnan(atr_values[i]) else current_close * 0.01
            signal = signals[i]
            confidence = confidences[i]

            # 1. Manage active position (Check SL and TP against intrabar High/Low)
            if active_trade is not None:
                hit_sl = current_low <= sl_price
                hit_tp = current_high >= tp_price
                signal_exit = (signal == -1)

                exit_triggered = False
                exit_price = current_close
                exit_reason = ""

                # Conservative assumption: if both high and low hit bounds, check gap or treat as SL
                if hit_sl and hit_tp:
                    # Intrabar collision: assign based on open
                    if abs(current_open - sl_price) < abs(current_open - tp_price):
                        exit_price = sl_price * (1 - self.slippage)
                        exit_reason = "STOP_LOSS"
                    else:
                        exit_price = tp_price * (1 - self.slippage)
                        exit_reason = "TAKE_PROFIT"
                    exit_triggered = True
                elif hit_sl:
                    exit_price = sl_price * (1 - self.slippage)
                    exit_reason = "STOP_LOSS"
                    exit_triggered = True
                elif hit_tp:
                    exit_price = tp_price * (1 - self.slippage)
                    exit_reason = "TAKE_PROFIT"
                    exit_triggered = True
                elif signal_exit:
                    exit_price = current_close * (1 - self.slippage)
                    exit_reason = "SIGNAL_EXIT"
                    exit_triggered = True
                elif i == n - 1: # End of simulation
                    exit_price = current_close
                    exit_reason = "END_OF_DATA"
                    exit_triggered = True

                if exit_triggered:
                    exit_fee = exit_price * active_trade.size * self.fee_rate
                    gross_pnl = (exit_price - active_trade.entry_price) * active_trade.size
                    net_pnl = gross_pnl - active_trade.fee_paid - exit_fee
                    cash += (active_trade.size * exit_price) - exit_fee

                    active_trade.exit_time = current_time
                    active_trade.exit_price = exit_price
                    active_trade.pnl = net_pnl
                    invested = active_trade.entry_price * active_trade.size
                    active_trade.pnl_pct = (net_pnl / invested) * 100 if invested > 0 else 0.0
                    active_trade.fee_paid += exit_fee
                    active_trade.exit_reason = exit_reason
                    active_trade.duration_bars = i - entry_idx

                    trades.append(active_trade)
                    active_trade = None

            # 2. Check for New Entry Signal
            if active_trade is None and signal == 1 and i < n - 1:
                # Calculate risk amount
                current_equity = cash
                risk_amount = current_equity * self.config.risk_per_trade
                atr_dist = max(current_atr * self.config.sl_atr_multiplier, current_close * 0.005)
                
                # Sizing: risk_amount / per_unit_risk
                size = risk_amount / atr_dist
                cost = size * current_close

                # Bound size by available cash
                max_affordable = (cash * 0.98) / current_close
                if size > max_affordable:
                    size = max_affordable

                if size * current_close > 20.0: # Minimum order threshold $20
                    entry_price = current_close * (1 + self.slippage)
                    entry_fee = entry_price * size * self.fee_rate
                    cash -= (entry_price * size + entry_fee)

                    sl_price = entry_price - (self.config.sl_atr_multiplier * current_atr)
                    tp_price = entry_price + (self.config.tp_atr_multiplier * current_atr)
                    entry_idx = i

                    active_trade = TradeRecord(
                        entry_time=current_time,
                        entry_price=entry_price,
                        size=size,
                        side="LONG",
                        fee_paid=entry_fee
                    )

            # 3. Calculate portfolio equity at this bar
            unrealized_pnl = 0.0
            if active_trade is not None:
                unrealized_pnl = (current_close - active_trade.entry_price) * active_trade.size

            total_equity = cash + (active_trade.size * current_close if active_trade else 0.0)
            equity_records.append({
                'datetime': current_time,
                'equity': total_equity,
                'cash': cash,
                'close': current_close
            })

        # Process Results
        equity_df = pd.DataFrame(equity_records).set_index('datetime')
        trades_df = pd.DataFrame([t.__dict__ for t in trades])

        # Benchmark Buy & Hold
        buy_hold_ret = ((close_prices[-1] - close_prices[0]) / close_prices[0]) * 100.0

        # Drawdown calculation
        equity_series = equity_df['equity']
        rolling_max = equity_series.cummax()
        drawdown = (equity_series - rolling_max) / rolling_max
        max_drawdown = float(drawdown.min() * 100.0)
        equity_df['drawdown_pct'] = drawdown * 100.0

        # Total Return
        final_balance = float(equity_series.iloc[-1])
        initial_balance = self.config.initial_balance
        total_return_pct = ((final_balance - initial_balance) / initial_balance) * 100.0

        # Sharpe Ratio (daily/periodic returns)
        pct_returns = equity_series.pct_change().dropna()
        if len(pct_returns) > 1 and pct_returns.std() > 0:
            sharpe_ratio = float((pct_returns.mean() / pct_returns.std()) * np.sqrt(365 * 24 if 'h' in str(df.index.freq) else 252))
        else:
            sharpe_ratio = 0.0

        # Win rate & Profit factor
        if len(trades_df) > 0:
            winning_trades = int((trades_df['pnl'] > 0).sum())
            losing_trades = int((trades_df['pnl'] <= 0).sum())
            win_rate = (winning_trades / len(trades_df)) * 100.0

            gross_profit = float(trades_df.loc[trades_df['pnl'] > 0, 'pnl'].sum())
            gross_loss = abs(float(trades_df.loc[trades_df['pnl'] < 0, 'pnl'].sum()))
            profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 1.0)
        else:
            winning_trades = 0
            losing_trades = 0
            win_rate = 0.0
            profit_factor = 0.0

        return BacktestResult(
            initial_balance=initial_balance,
            final_balance=round(final_balance, 2),
            total_return_pct=round(total_return_pct, 2),
            buy_hold_return_pct=round(buy_hold_ret, 2),
            max_drawdown_pct=round(abs(max_drawdown), 2),
            sharpe_ratio=round(sharpe_ratio, 2),
            profit_factor=round(profit_factor, 2),
            win_rate_pct=round(win_rate, 2),
            total_trades=len(trades_df),
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            equity_curve=equity_df,
            trades_df=trades_df
        )
