"""
AI bottrade - Visualization and Helper Utilities
Produces interactive Plotly charts for Candlestick Price Action, AI Signals,
Equity Curve vs Benchmark, Drawdowns, and Indicator Subplots.
"""
from typing import Optional
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def plot_price_and_signals(
    df: pd.DataFrame,
    signals: Optional[np.ndarray] = None,
    trades_df: Optional[pd.DataFrame] = None,
    trade_setup: Optional[any] = None,
    title: str = "Price Chart & AI Signals"
) -> go.Figure:
    """
    Creates an interactive candlestick chart with EMAs, Bollinger Bands, and Signal Markers.
    """
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.75, 0.25],
        subplot_titles=(title, "RSI (14)")
    )

    # 1. Candlestick
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            name="OHLC",
            increasing_line_color="#26a69a",
            decreasing_line_color="#ef5350"
        ),
        row=1, col=1
    )

    # 2. EMAs
    if 'ema_21' in df.columns:
        fig.add_trace(
            go.Scatter(x=df.index, y=df['ema_21'], line=dict(color='#ff9800', width=1.2), name="EMA 21"),
            row=1, col=1
        )
    if 'ema_50' in df.columns:
        fig.add_trace(
            go.Scatter(x=df.index, y=df['ema_50'], line=dict(color='#2196f3', width=1.2), name="EMA 50"),
            row=1, col=1
        )
    if 'ema_200' in df.columns:
        fig.add_trace(
            go.Scatter(x=df.index, y=df['ema_200'], line=dict(color='#9c27b0', width=1.5), name="EMA 200"),
            row=1, col=1
        )

    # 3. Bollinger Bands
    if 'bb_upper' in df.columns and 'bb_lower' in df.columns:
        fig.add_trace(
            go.Scatter(x=df.index, y=df['bb_upper'], line=dict(color='rgba(150, 150, 150, 0.3)', width=1), name="BB Upper"),
            row=1, col=1
        )
        fig.add_trace(
            go.Scatter(x=df.index, y=df['bb_lower'], line=dict(color='rgba(150, 150, 150, 0.3)', width=1),
                       fill='tonexty', fillcolor='rgba(150, 150, 150, 0.05)', name="BB Lower"),
            row=1, col=1
        )

    # 4. Smart Money Concepts (SMC) Visual Overlays
    if 'bos_bullish' in df.columns:
        bos_bull_bars = df[df['bos_bullish']]
        if not bos_bull_bars.empty:
            fig.add_trace(
                go.Scatter(
                    x=bos_bull_bars.index,
                    y=bos_bull_bars['high'] * 1.002,
                    mode='markers+text',
                    marker=dict(symbol='diamond', size=8, color='#00e5ff'),
                    text=["BOS" for _ in range(len(bos_bull_bars))],
                    textposition="top center",
                    textfont=dict(size=9, color='#00e5ff'),
                    name="SMC BOS (Bullish)"
                ),
                row=1, col=1
            )

    if 'bos_bearish' in df.columns:
        bos_bear_bars = df[df['bos_bearish']]
        if not bos_bear_bars.empty:
            fig.add_trace(
                go.Scatter(
                    x=bos_bear_bars.index,
                    y=bos_bear_bars['low'] * 0.998,
                    mode='markers+text',
                    marker=dict(symbol='diamond', size=8, color='#ff1744'),
                    text=["BOS" for _ in range(len(bos_bear_bars))],
                    textposition="bottom center",
                    textfont=dict(size=9, color='#ff1744'),
                    name="SMC BOS (Bearish)"
                ),
                row=1, col=1
            )

    if 'choch_bullish' in df.columns:
        choch_bull_bars = df[df['choch_bullish']]
        if not choch_bull_bars.empty:
            fig.add_trace(
                go.Scatter(
                    x=choch_bull_bars.index,
                    y=choch_bull_bars['high'] * 1.003,
                    mode='markers+text',
                    marker=dict(symbol='star-diamond', size=10, color='#76ff03'),
                    text=["CHoCH" for _ in range(len(choch_bull_bars))],
                    textposition="top center",
                    textfont=dict(size=10, color='#76ff03'),
                    name="SMC CHoCH (Bullish Reversal)"
                ),
                row=1, col=1
            )

    if 'choch_bearish' in df.columns:
        choch_bear_bars = df[df['choch_bearish']]
        if not choch_bear_bars.empty:
            fig.add_trace(
                go.Scatter(
                    x=choch_bear_bars.index,
                    y=choch_bear_bars['low'] * 0.997,
                    mode='markers+text',
                    marker=dict(symbol='star-diamond', size=10, color='#d500f9'),
                    text=["CHoCH" for _ in range(len(choch_bear_bars))],
                    textposition="bottom center",
                    textfont=dict(size=10, color='#d500f9'),
                    name="SMC CHoCH (Bearish Reversal)"
                ),
                row=1, col=1
            )

    # 5. Markers from backtest trades
    if trades_df is not None and not trades_df.empty:
        # Buy Entries
        buy_times = trades_df['entry_time']
        buy_prices = trades_df['entry_price']
        fig.add_trace(
            go.Scatter(
                x=buy_times,
                y=buy_prices * 0.995,
                mode='markers',
                marker=dict(symbol='triangle-up', size=13, color='#00e676', line=dict(width=1, color='white')),
                name="AI/SMC Buy Entry",
                text=[f"Size: {s:.3f}" for s in trades_df['size']]
            ),
            row=1, col=1
        )

        # Exits
        exits = trades_df.dropna(subset=['exit_time'])
        if not exits.empty:
            tp_exits = exits[exits['exit_reason'] == 'TAKE_PROFIT']
            sl_exits = exits[exits['exit_reason'] == 'STOP_LOSS']
            other_exits = exits[~exits['exit_reason'].isin(['TAKE_PROFIT', 'STOP_LOSS'])]

            if not tp_exits.empty:
                fig.add_trace(
                    go.Scatter(
                        x=tp_exits['exit_time'],
                        y=tp_exits['exit_price'] * 1.005,
                        mode='markers',
                        marker=dict(symbol='star', size=11, color='#ffd600'),
                        name="Take Profit"
                    ),
                    row=1, col=1
                )
            if not sl_exits.empty:
                fig.add_trace(
                    go.Scatter(
                        x=sl_exits['exit_time'],
                        y=sl_exits['exit_price'] * 1.005,
                        mode='markers',
                        marker=dict(symbol='x', size=10, color='#ff1744'),
                        name="Stop Loss"
                    ),
                    row=1, col=1
                )
            if not other_exits.empty:
                fig.add_trace(
                    go.Scatter(
                        x=other_exits['exit_time'],
                        y=other_exits['exit_price'] * 1.005,
                        mode='markers',
                        marker=dict(symbol='triangle-down', size=11, color='#ff9100'),
                        name="Signal Exit"
                    ),
                    row=1, col=1
                )

    # 6. RSI Subplot
    if 'rsi' in df.columns:
        fig.add_trace(
            go.Scatter(x=df.index, y=df['rsi'], line=dict(color='#ab47bc', width=1.5), name="RSI (14)"),
            row=2, col=1
        )
        fig.add_hline(y=70, line_dash="dash", line_color="rgba(239, 83, 80, 0.6)", row=2, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="rgba(38, 166, 154, 0.6)", row=2, col=1)

    # 7. Real-time Trade Setup Levels (Entry, SL, TP1, TP2)
    if trade_setup is not None and getattr(trade_setup, 'status', '') == "ACTIVE_SETUP":
        # Entry Line
        fig.add_hline(
            y=trade_setup.entry_price,
            line_dash="dot",
            line_color="#00e5ff",
            line_width=1.8,
            annotation_text=f"🎯 ENTRY: ${trade_setup.entry_price:,.2f}",
            annotation_position="top right",
            annotation_font=dict(color="#00e5ff", size=10),
            row=1, col=1
        )
        # Stop Loss Line
        fig.add_hline(
            y=trade_setup.stop_loss,
            line_dash="dash",
            line_color="#ff1744",
            line_width=1.8,
            annotation_text=f"🛑 SL: ${trade_setup.stop_loss:,.2f} (-{trade_setup.sl_pct:.2f}%)",
            annotation_position="bottom right",
            annotation_font=dict(color="#ff1744", size=10),
            row=1, col=1
        )
        # Take Profit 1 Line (1:2 R:R)
        fig.add_hline(
            y=trade_setup.take_profit_1,
            line_dash="dash",
            line_color="#ffd600",
            line_width=1.8,
            annotation_text=f"🏆 TP1 (1:2): ${trade_setup.take_profit_1:,.2f} (+{trade_setup.tp1_pct:.2f}%)",
            annotation_position="top right",
            annotation_font=dict(color="#ffd600", size=10),
            row=1, col=1
        )
        # Take Profit 2 Line (1:3 R:R)
        fig.add_hline(
            y=trade_setup.take_profit_2,
            line_dash="dash",
            line_color="#00e676",
            line_width=1.8,
            annotation_text=f"🚀 TP2 (1:3): ${trade_setup.take_profit_2:,.2f} (+{trade_setup.tp2_pct:.2f}%)",
            annotation_position="top right",
            annotation_font=dict(color="#00e676", size=10),
            row=1, col=1
        )

    fig.update_layout(
        template="plotly_dark",
        xaxis_rangeslider_visible=False,
        height=720,
        margin=dict(l=40, r=40, t=50, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig


def plot_equity_curve(equity_df: pd.DataFrame, initial_balance: float = 10000.0) -> go.Figure:
    """
    Plots portfolio equity curve compared with Buy & Hold benchmark, plus Drawdown chart.
    """
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.7, 0.3],
        subplot_titles=("Portfolio Equity ($)", "Drawdown (%)")
    )

    # Equity Curve
    fig.add_trace(
        go.Scatter(
            x=equity_df.index,
            y=equity_df['equity'],
            line=dict(color='#00e676', width=2),
            name="AI Bot Equity",
            fill='tozeroy',
            fillcolor='rgba(0, 230, 118, 0.08)'
        ),
        row=1, col=1
    )

    # Benchmark Buy & Hold
    if 'close' in equity_df.columns:
        first_close = equity_df['close'].iloc[0]
        benchmark = (equity_df['close'] / first_close) * initial_balance
        fig.add_trace(
            go.Scatter(
                x=equity_df.index,
                y=benchmark,
                line=dict(color='#9e9e9e', width=1.2, dash='dot'),
                name="Buy & Hold Benchmark"
            ),
            row=1, col=1
        )

    # Drawdown Chart
    if 'drawdown_pct' in equity_df.columns:
        fig.add_trace(
            go.Scatter(
                x=equity_df.index,
                y=equity_df['drawdown_pct'],
                line=dict(color='#ff5252', width=1.2),
                fill='tozeroy',
                fillcolor='rgba(255, 82, 82, 0.2)',
                name="Drawdown %"
            ),
            row=2, col=1
        )

    fig.update_layout(
        template="plotly_dark",
        xaxis_rangeslider_visible=False,
        height=500,
        margin=dict(l=40, r=40, t=50, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig


def plot_feature_importance(imp_df: pd.DataFrame, top_n: int = 12) -> go.Figure:
    """Plots top N feature importances from the AI model"""
    top = imp_df.head(top_n).sort_values('importance', ascending=True)
    fig = go.Figure(go.Bar(
        x=top['importance'],
        y=top['feature'],
        orientation='h',
        marker=dict(color='#29b6f6')
    ))
    fig.update_layout(
        title=f"Top {top_n} AI Feature Importances",
        template="plotly_dark",
        height=380,
        margin=dict(l=100, r=30, t=50, b=30)
    )
    return fig
