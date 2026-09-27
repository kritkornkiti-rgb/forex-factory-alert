"""
AI bottrade - Command Line Interface (CLI)
Allows running AI training, backtesting, and paper trading from terminal.
"""
import argparse
import sys
import time
from pathlib import Path
from typing import List, Optional
import pandas as pd

from src.config import SUPPORTED_ASSETS, SUPPORTED_TIMEFRAMES, TradingConfig, MODELS_DIR
from src.data_loader import MarketDataLoader
from src.feature_engineering import FeatureEngineer
from src.model import AITradingModel
from src.backtester import BacktestEngine
from src.paper_trader import PaperTrader


def get_model_path(asset: str, timeframe: str) -> Path:
    slug = asset.replace("/", "_").replace(" ", "_").lower()
    return MODELS_DIR / f"{slug}_{timeframe}_model.joblib"


def cmd_list_assets():
    print("=" * 60)
    print("Supported Assets in AI bottrade:")
    print("=" * 60)
    for name, info in SUPPORTED_ASSETS.items():
        cat = info['category'].upper()
        src = info['source'].upper()
        fee = f"{info['fee_rate']*100:.3f}%"
        print(f" • {name:<22} | Category: {cat:<6} | Source: {src:<8} | Fee: {fee}")
    print("\nSupported Timeframes:", ", ".join(SUPPORTED_TIMEFRAMES))


def cmd_train(asset: str, timeframe: str, model_type: str):
    print(f"\n[AI bottrade] Starting Model Training for: {asset} ({timeframe})")
    loader = MarketDataLoader()
    df = loader.fetch_data(asset, timeframe=timeframe, limit=2000, force_download=False)
    print(f"Loaded {len(df)} candles for {asset}.")

    fe = FeatureEngineer()
    df_feat, feature_cols = fe.prepare_features(df, include_target=True)
    print(f"Generated {len(feature_cols)} features across {len(df_feat)} labeled samples.")

    model = AITradingModel(model_type=model_type)
    metrics = model.train(df_feat, feature_cols)

    save_path = get_model_path(asset, timeframe)
    model.save(save_path)

    print("\n" + "=" * 50)
    print(" TRAINING SUMMARY")
    print("=" * 50)
    print(f"Out-of-sample Test Accuracy : {metrics.accuracy:.2%}")
    print(f"Macro F1-Score              : {metrics.f1_macro:.3f}")
    if metrics.cv_scores:
        print(f"Cross-Val Accuracy (Mean)   : {sum(metrics.cv_scores)/len(metrics.cv_scores):.2%}")
    print(f"Saved Checkpoint to         : {save_path}")
    print("=" * 50 + "\n")


def cmd_backtest(
    asset: str,
    timeframe: str,
    risk: float,
    sl_atr: float,
    tp_atr: float,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    print(f"\n[AI bottrade] Running Backtest for: {asset} ({timeframe})")
    save_path = get_model_path(asset, timeframe)
    
    loader = MarketDataLoader()
    df = loader.fetch_data(asset, timeframe=timeframe, limit=2000)
    fe = FeatureEngineer()
    df_feat, feature_cols = fe.prepare_features(df, include_target=True)

    if not save_path.exists():
        print(f"No existing trained model found at {save_path.name}. Training a new model first...")
        model = AITradingModel()
        model.train(df_feat, feature_cols)
        model.save(save_path)
    else:
        model = AITradingModel.load(save_path)

    signals, confidences = model.predict_series(df_feat)

    # Date Range Slicing for Backtest
    df_feat_bt = df_feat
    signals_bt = signals
    confidences_bt = confidences

    if start_date or end_date:
        mask = pd.Series(True, index=df_feat.index)
        if start_date:
            ts_start = pd.to_datetime(start_date)
            if df_feat.index.tz is not None and ts_start.tz is None:
                ts_start = ts_start.tz_localize(df_feat.index.tz)
            mask = mask & (df_feat.index >= ts_start)
        if end_date:
            ts_end = pd.to_datetime(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
            if df_feat.index.tz is not None and ts_end.tz is None:
                ts_end = ts_end.tz_localize(df_feat.index.tz)
            mask = mask & (df_feat.index <= ts_end)

        df_feat_bt = df_feat[mask]
        signals_bt = signals[mask.values]
        confidences_bt = confidences[mask.values]

        if len(df_feat_bt) < 15:
            print(f"[Error] The selected date range contains fewer than 15 bars ({len(df_feat_bt)} found). Please select a wider range.")
            return

    config = TradingConfig(
        risk_per_trade=risk,
        sl_atr_multiplier=sl_atr,
        tp_atr_multiplier=tp_atr
    )
    asset_info = SUPPORTED_ASSETS.get(asset, {})
    fee_rate = asset_info.get("fee_rate", 0.00075)

    engine = BacktestEngine(config=config, fee_rate=fee_rate)
    result = engine.run(df_feat_bt, signals_bt, confidences_bt)

    # SMC Market Status
    latest = df_feat_bt.iloc[-1]
    struct_str = "BULLISH 🟢" if latest.get('smc_structure', 1) == 1 else "BEARISH 🔴"
    range_pos = latest.get('range_position', 0.5) * 100
    zone_str = f"DISCOUNT ({range_pos:.1f}%) 🟢" if range_pos < 50 else f"PREMIUM ({range_pos:.1f}%) 🔴"
    in_ob = "Bullish OB Retest" if latest.get('in_bullish_ob') else ("Bearish OB Retest" if latest.get('in_bearish_ob') else "Neutral")
    fvg_str = "Active Bullish FVG" if latest.get('fvg_bullish') else ("Active Bearish FVG" if latest.get('fvg_bearish') else "None")

    print("\n" + "=" * 55)
    print(f" BACKTEST PERFORMANCE REPORT: {asset}")
    print(f" Period: {df_feat_bt.index[0].strftime('%Y-%m-%d %H:%M')} to {df_feat_bt.index[-1].strftime('%Y-%m-%d %H:%M')} ({len(df_feat_bt)} bars)")
    print("=" * 55)
    print(f" SMC Market Structure  : {struct_str}")
    print(f" Dealing Range Zone    : {zone_str}")
    print(f" Order Block Status    : {in_ob}")
    print(f" Fair Value Gap (FVG)  : {fvg_str}")
    print("-" * 55)
    print(f" Initial Balance       : ${result.initial_balance:,.2f}")
    print(f" Final Balance         : ${result.final_balance:,.2f}")
    print(f" Total Return          : {result.total_return_pct:+.2f}%")
    print(f" Buy & Hold Benchmark  : {result.buy_hold_return_pct:+.2f}%")
    print(f" Max Drawdown          : {result.max_drawdown_pct:.2f}%")
    print(f" Sharpe Ratio          : {result.sharpe_ratio:.2f}")
    print(f" Profit Factor         : {result.profit_factor:.2f}")
    print(f" Win Rate              : {result.win_rate_pct:.2f}%")
    print(f" Total Trades          : {result.total_trades} (Won: {result.winning_trades}, Lost: {result.losing_trades})")
    print("=" * 55)

    if result.total_trades > 0:
        print("\nLast 5 Executed Trades:")
        cols_to_show = ['entry_time', 'exit_time', 'entry_price', 'exit_price', 'pnl', 'pnl_pct', 'exit_reason']
        print(result.trades_df[cols_to_show].tail(5).to_string(index=False))
    print()


def cmd_paper_trade(asset: str, timeframe: str, step_once: bool, poll_interval: int):
    print(f"\n[AI bottrade] Starting Paper Trading Session for: {asset} ({timeframe})")
    save_path = get_model_path(asset, timeframe)
    if not save_path.exists():
        print(f"Model not found. Please run 'python main.py train --asset \"{asset}\"' first.")
        return

    model = AITradingModel.load(save_path)
    trader = PaperTrader(asset_name=asset, timeframe=timeframe, model=model)

    print(f"Current Virtual Balance: ${trader.cash:,.2f}")
    if trader.open_position:
        print(f"Active Position: {trader.open_position}")

    if step_once:
        res = trader.step()
        print("\nPaper Trade Step Result:")
        print(res)
    else:
        print(f"Starting continuous polling (every {poll_interval}s). Press Ctrl+C to stop.\n")
        try:
            while True:
                res = trader.step()
                t = res.get('timestamp', '')
                p = res.get('price', 0.0)
                sig = res.get('ai_signal', 'HOLD')
                conf = res.get('confidence', 0.0)
                act = res.get('action_taken', 'NONE')
                eq = res.get('total_equity', 0.0)
                print(f"[{t}] Price: ${p:,.2f} | AI: {sig} ({conf:.1%}) | Action: {act} | Portfolio: ${eq:,.2f}")
                time.sleep(poll_interval)
        except KeyboardInterrupt:
            print("\nPaper trading stopped by user.")


from src.continuous_learning import ContinuousLearner


def cmd_continual_learn(asset: str, timeframe: str):
    print(f"\n[AI bottrade] Initiating Continual Learning Retrain for: {asset} ({timeframe})")
    save_path = get_model_path(asset, timeframe)
    if not save_path.exists():
        print("No existing model found. Initializing base model...")
        model = AITradingModel()
    else:
        model = AITradingModel.load(save_path)

    learner = ContinuousLearner(asset_name=asset, timeframe=timeframe)
    updated_model, metrics = learner.retrain_model_continual(model)
    summary = learner.get_learning_summary()
    print("\n" + "=" * 50)
    print(" CONTINUAL LEARNING UPGRADE REPORT")
    print("=" * 50)
    print(f" Model Version        : v{summary['model_version']}")
    print(f" Retrain Test Accuracy: {metrics.accuracy:.2%}")
    print(f" Macro F1 Score       : {metrics.f1_macro:.3f}")
    print(f" Adaptive Confidence  : {summary['adaptive_confidence']:.1%}")
    print(f" Experience Buffer    : {summary['total_experiences']} trade outcomes learned")
    print("=" * 50 + "\n")


from src.trade_setup import TradeSetupGenerator


def cmd_trade_setup(asset: str, timeframe: str, capital: float, risk: float):
    print(f"\n[AI bottrade] Calculating Real-time Trade Setup for: {asset} ({timeframe})")
    loader = MarketDataLoader()
    df_raw = loader.fetch_data(asset, timeframe=timeframe, limit=300, force_download=True)
    fe = FeatureEngineer()
    df_feat, cols = fe.prepare_features(df_raw, include_target=False)

    save_path = get_model_path(asset, timeframe)
    if not save_path.exists():
        print("Training model checkpoint first...")
        df_train, train_cols = fe.prepare_features(df_raw, include_target=True)
        model = AITradingModel()
        model.train(df_train, train_cols)
        model.save(save_path)
    else:
        model = AITradingModel.load(save_path)

    gen = TradeSetupGenerator()
    setup = gen.generate_setup(asset, timeframe, df_feat, model, capital=capital, risk_pct=risk)

    print("\n" + "=" * 60)
    print(f" 🎯 AI REAL-TIME TRADE SETUP CARD: {asset}")
    print("=" * 60)
    print(f" Signal / Status     : {setup.direction} ({setup.status})")
    print(f" AI Model Confidence : {setup.ai_confidence:.1%}")
    print(f" Confluence Score    : {setup.confluence_score}/{setup.total_confluences}")
    print("-" * 60)
    print(f" 🎯 ENTRY PRICE      : ${setup.entry_price:,.2f} ({setup.entry_type})")
    if setup.direction != "NEUTRAL (WAIT)":
        print(f" 🛑 STOP LOSS (SL)   : ${setup.stop_loss:,.2f} (Distance: -${setup.sl_distance:.2f} / -{setup.sl_pct:.2f}%)")
        print(f" 🏆 TAKE PROFIT 1    : ${setup.take_profit_1:,.2f} (+${setup.tp1_distance:.2f} / +{setup.tp1_pct:.2f}%) [R:R 1:{setup.tp1_rr:.1f}]")
        print(f" 🚀 TAKE PROFIT 2    : ${setup.take_profit_2:,.2f} (+${setup.tp2_distance:.2f} / +{setup.tp2_pct:.2f}%) [R:R 1:{setup.tp2_rr:.1f}]")
        print(f" 💼 RECOMMENDED SIZE : {setup.recommended_size:.4f} units (Value: ${setup.position_value:,.2f})")
        print(f" 🛡️ MAX RISK CAPITAL : ${setup.risk_amount:,.2f} ({risk*100:.1f}% of ${capital:,.2f})")
    print("-" * 60)
    print(" SMC Confluence Checklist:")
    for conf in setup.confluence_list:
        icon = "✅" if conf['passed'] else "❌"
        print(f"   {icon} {conf['name']}: {conf['detail']}")
    print("\n AI Rationale:")
    print(f"   {setup.rationale_th}")
    print("=" * 60 + "\n")


from src.live_monitor import LiveMarketMonitor


def cmd_monitor(assets: List[str], timeframes: List[str], interval: int, once: bool):
    monitor = LiveMarketMonitor(assets=assets, timeframes=timeframes, check_interval_seconds=interval)
    if once:
        print(f"\n[AI bottrade] Running single-pass market scan for {assets} across ({', '.join(timeframes)})...")
        results = monitor.run_single_pass()
        for r in results:
            print(f"[{r['asset']} ({r['timeframe']})] Price: ${r['price']:,.2f} | Signal: {r['signal']} | Confluence: {r['confluence_score']}")
    else:
        monitor.start_monitoring_loop()


def main():
    parser = argparse.ArgumentParser(description="AI bottrade - AI Trading Bot for Crypto & Precious Metals")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # list
    subparsers.add_parser("list-assets", help="List all supported crypto and metal assets")

    # setup
    setup_parser = subparsers.add_parser("setup", help="Calculate exact Entry, SL, TP1, TP2 levels and position size")
    setup_parser.add_argument("--asset", type=str, default="GOLD (XAU/USD)", help="Asset name")
    setup_parser.add_argument("--timeframe", type=str, default="1h", choices=SUPPORTED_TIMEFRAMES)
    setup_parser.add_argument("--capital", type=float, default=10000.0, help="Account capital in USD")
    setup_parser.add_argument("--risk", type=float, default=0.02, help="Risk per trade (e.g. 0.02 for 2%)")

    # monitor
    mon_parser = subparsers.add_parser("monitor", help="24/7 continuous market monitoring & instant alerts")
    mon_parser.add_argument("--assets", nargs="+", default=None, help="Assets to monitor (defaults to saved settings from web dashboard)")
    mon_parser.add_argument("--timeframe", type=str, default=None, help="Single timeframe")
    mon_parser.add_argument("--timeframes", nargs="+", default=None, help="Multiple timeframes e.g. 15m 1h")
    mon_parser.add_argument("--interval", type=int, default=60, help="Check interval in seconds")
    mon_parser.add_argument("--once", action="store_true", help="Run a single pass and exit")

    # train
    train_parser = subparsers.add_parser("train", help="Train AI model on historical data")
    train_parser.add_argument("--asset", type=str, default="GOLD (XAU/USD)", help="Asset name")
    train_parser.add_argument("--timeframe", type=str, default="1h", choices=SUPPORTED_TIMEFRAMES)
    train_parser.add_argument("--model-type", type=str, default="gradient_boosting", choices=["gradient_boosting", "random_forest"])

    # continual-learn
    learn_parser = subparsers.add_parser("continual-learn", help="Incremental retraining on fresh market data and trade feedback")
    learn_parser.add_argument("--asset", type=str, default="GOLD (XAU/USD)", help="Asset name")
    learn_parser.add_argument("--timeframe", type=str, default="1h", choices=SUPPORTED_TIMEFRAMES)

    # backtest
    bt_parser = subparsers.add_parser("backtest", help="Run backtest simulation")
    bt_parser.add_argument("--asset", type=str, default="GOLD (XAU/USD)", help="Asset name")
    bt_parser.add_argument("--timeframe", type=str, default="1h", choices=SUPPORTED_TIMEFRAMES)
    bt_parser.add_argument("--risk", type=float, default=0.02, help="Risk per trade (e.g. 0.02 for 2%)")
    bt_parser.add_argument("--sl-atr", type=float, default=1.5, help="Stop loss ATR multiplier")
    bt_parser.add_argument("--tp-atr", type=float, default=2.5, help="Take profit ATR multiplier")
    bt_parser.add_argument("--start", type=str, default=None, help="Start date (YYYY-MM-DD)")
    bt_parser.add_argument("--end", type=str, default=None, help="End date (YYYY-MM-DD)")

    # paper-trade
    pt_parser = subparsers.add_parser("paper-trade", help="Run live paper trading")
    pt_parser.add_argument("--asset", type=str, default="GOLD (XAU/USD)", help="Asset name")
    pt_parser.add_argument("--timeframe", type=str, default="1h", choices=SUPPORTED_TIMEFRAMES)
    pt_parser.add_argument("--once", action="store_true", help="Run a single evaluation step and exit")
    pt_parser.add_argument("--interval", type=int, default=60, help="Polling interval in seconds")

    args = parser.parse_args()

    if args.command == "list-assets":
        cmd_list_assets()
    elif args.command == "setup":
        cmd_trade_setup(args.asset, args.timeframe, args.capital, args.risk)
    elif args.command == "monitor":
        tfs = args.timeframes or ([args.timeframe] if args.timeframe else None)
        cmd_monitor(args.assets, tfs, args.interval, args.once)
    elif args.command == "train":
        cmd_train(args.asset, args.timeframe, args.model_type)
    elif args.command == "continual-learn":
        cmd_continual_learn(args.asset, args.timeframe)
    elif args.command == "backtest":
        cmd_backtest(args.asset, args.timeframe, args.risk, args.sl_atr, args.tp_atr, args.start, args.end)
    elif args.command == "paper-trade":
        cmd_paper_trade(args.asset, args.timeframe, args.once, args.interval)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
