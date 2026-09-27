"""
AI bottrade - Interactive Web Dashboard
Powered by Streamlit and Plotly.
Supports Backtesting, AI Training, Real-time Paper Trading for Crypto & Precious Metals.
"""
from datetime import datetime, timedelta
import json
from pathlib import Path
import pandas as pd
import streamlit as st

from src.config import SUPPORTED_ASSETS, SUPPORTED_TIMEFRAMES, TradingConfig, MODELS_DIR, DATA_DIR
from src.data_loader import MarketDataLoader
from src.feature_engineering import FeatureEngineer
from src.model import AITradingModel
from src.backtester import BacktestEngine
from src.continuous_learning import ContinuousLearner
from src.paper_trader import PaperTrader
from src.trade_setup import TradeSetupGenerator
from src.notifier import AlertNotifier
from src.live_monitor import LiveMarketMonitor
from src.utils import plot_price_and_signals, plot_equity_curve, plot_feature_importance

# Page configuration
st.set_page_config(
    page_title="AI bottrade - AI Trading System",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for modern styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        background: linear-gradient(90deg, #00c6ff, #0072ff);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        color: #90a4ae;
        font-size: 1.05rem;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #1e222d;
        border-radius: 8px;
        padding: 15px;
        border: 1px solid #2a2e39;
    }
    .status-badge-buy {
        background-color: #00e676;
        color: #000;
        padding: 4px 12px;
        border-radius: 12px;
        font-weight: bold;
    }
    .status-badge-sell {
        background-color: #ff1744;
        color: #fff;
        padding: 4px 12px;
        border-radius: 12px;
        font-weight: bold;
    }
    .status-badge-hold {
        background-color: #ffb300;
        color: #000;
        padding: 4px 12px;
        border-radius: 12px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)


def get_model_path(asset: str, timeframe: str) -> Path:
    slug = asset.replace("/", "_").replace(" ", "_").lower()
    return MODELS_DIR / f"{slug}_{timeframe}_model.joblib"


def main():
    st.markdown('<div class="main-header">🤖 AI bottrade</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Institutional Smart Money Concepts (SMC) + Machine Learning Trading System for Crypto & Precious Metals</div>', unsafe_allow_html=True)

    # Sidebar Controls
    st.sidebar.header("⚙️ Configuration & Settings")

    # Asset Selection
    asset_list = list(SUPPORTED_ASSETS.keys())
    # Group assets nicely
    metals = [a for a in asset_list if SUPPORTED_ASSETS[a]['category'] == 'metal']
    cryptos = [a for a in asset_list if SUPPORTED_ASSETS[a]['category'] == 'crypto']

    selected_asset = st.sidebar.selectbox(
        "📊 Select Asset",
        options=metals + cryptos,
        index=0,
        help="Select between Crypto pairs and Precious Metals"
    )

    selected_tf = st.sidebar.selectbox(
        "⏱️ Timeframe",
        options=SUPPORTED_TIMEFRAMES,
        index=1,
        help="Bar timeframe (15m, 1h, 4h, 1d)"
    )

    asset_info = SUPPORTED_ASSETS[selected_asset]
    st.sidebar.caption(f"Category: **{asset_info['category'].upper()}** | Source: **{asset_info['source'].upper()}** | Est. Fee: **{asset_info['fee_rate']*100:.3f}%**")

    st.sidebar.markdown("---")
    st.sidebar.subheader("🛡️ Risk Management")

    initial_capital = st.sidebar.number_input("Initial Capital ($)", min_value=100.0, max_value=1000000.0, value=10000.0, step=500.0)
    risk_pct = st.sidebar.slider("Risk Per Trade (%)", min_value=0.5, max_value=10.0, value=2.0, step=0.5) / 100.0
    sl_atr = st.sidebar.slider("Stop-Loss (ATR Multiplier)", min_value=0.5, max_value=4.0, value=1.5, step=0.1)
    tp_atr = st.sidebar.slider("Take-Profit (ATR Multiplier)", min_value=1.0, max_value=6.0, value=2.5, step=0.1)
    conf_thresh = st.sidebar.slider("AI Confidence Threshold", min_value=0.40, max_value=0.85, value=0.52, step=0.01)

    st.sidebar.markdown("---")
    st.sidebar.subheader("🧠 Model Settings")
    model_type = st.sidebar.selectbox("AI Model Architecture", ["gradient_boosting", "random_forest"])
    force_fresh_data = st.sidebar.checkbox("Force Fresh Data Download", value=False)

    st.sidebar.markdown("---")
    st.sidebar.subheader("📅 Backtest Period (ช่วงเวลาย้อนหลัง)")
    period_options = [
        "ทั้งหมดที่มี (Max History)",
        "30 วันล่าสุด (Last 30 Days)",
        "90 วันล่าสุด (Last 90 Days)",
        "180 วันล่าสุด (Last 180 Days)",
        "1 ปีล่าสุด (Last 1 Year)",
        "กำหนดวันที่เอง (Custom Date Range)"
    ]
    period_choice = st.sidebar.selectbox("เลือกช่วงเวลาทดสอบ", options=period_options, index=0)

    start_date_filter = None
    end_date_filter = None

    if period_choice == "กำหนดวันที่เอง (Custom Date Range)":
        now_dt = datetime.now().date()
        c_d1, c_d2 = st.sidebar.columns(2)
        start_val = c_d1.date_input("วันเริ่มต้น", value=now_dt - timedelta(days=90))
        end_val = c_d2.date_input("วันสิ้นสุด", value=now_dt)
        if start_val and end_val:
            start_date_filter = pd.to_datetime(start_val)
            end_date_filter = pd.to_datetime(end_val) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    elif period_choice == "30 วันล่าสุด (Last 30 Days)":
        start_date_filter = pd.to_datetime(datetime.now() - timedelta(days=30))
    elif period_choice == "90 วันล่าสุด (Last 90 Days)":
        start_date_filter = pd.to_datetime(datetime.now() - timedelta(days=90))
    elif period_choice == "180 วันล่าสุด (Last 180 Days)":
        start_date_filter = pd.to_datetime(datetime.now() - timedelta(days=180))
    elif period_choice == "1 ปีล่าสุด (Last 1 Year)":
        start_date_filter = pd.to_datetime(datetime.now() - timedelta(days=365))

    trading_config = TradingConfig(
        initial_balance=initial_capital,
        risk_per_trade=risk_pct,
        sl_atr_multiplier=sl_atr,
        tp_atr_multiplier=tp_atr,
        confidence_threshold=conf_thresh
    )

    # Main Navigation Tabs
    tab_backtest, tab_paper, tab_learn, tab_alert, tab_data = st.tabs([
        "📊 Backtest & Strategy",
        "🟢 Live Paper Trading",
        "🧠 Continual Learning & Feedback",
        "🔔 24/7 Alerts & Telegram",
        "🔍 Market Indicators & Data"
    ])

    # TAB 1: BACKTEST & STRATEGY
    with tab_backtest:
        col_btn, col_info = st.columns([1, 3])
        with col_btn:
            run_btn = st.button("🚀 Train & Run Backtest", type="primary", use_container_width=True)

        if run_btn or 'last_backtest' not in st.session_state:
            with st.spinner(f"Fetching data and training AI model for {selected_asset}..."):
                try:
                    loader = MarketDataLoader()
                    df_raw = loader.fetch_data(selected_asset, timeframe=selected_tf, limit=2000, force_download=force_fresh_data)

                    fe = FeatureEngineer()
                    df_feat, feature_cols = fe.prepare_features(df_raw, include_target=True)

                    model_path = get_model_path(selected_asset, selected_tf)
                    model = AITradingModel(model_type=model_type, confidence_threshold=conf_thresh)
                    metrics = model.train(df_feat, feature_cols)
                    model.save(model_path)

                    signals, confidences = model.predict_series(df_feat)
                    fee_rate = asset_info.get("fee_rate", 0.00075)

                    # Date Range Slicing for Backtest
                    mask = pd.Series(True, index=df_feat.index)
                    if start_date_filter is not None:
                        s_ts = start_date_filter
                        if df_feat.index.tz is not None and s_ts.tz is None:
                            s_ts = s_ts.tz_localize(df_feat.index.tz)
                        mask = mask & (df_feat.index >= s_ts)
                    if end_date_filter is not None:
                        e_ts = end_date_filter
                        if df_feat.index.tz is not None and e_ts.tz is None:
                            e_ts = e_ts.tz_localize(df_feat.index.tz)
                        mask = mask & (df_feat.index <= e_ts)

                    df_feat_bt = df_feat[mask]
                    signals_bt = signals[mask.values]
                    confidences_bt = confidences[mask.values]

                    if len(df_feat_bt) < 15:
                        st.warning("⚠️ ข้อมูลในช่วงเวลาที่เลือกมีน้อยกว่า 15 แท่งเทียน กำลังใช้ข้อมูลทั้งหมดแทน")
                        df_feat_bt = df_feat
                        signals_bt = signals
                        confidences_bt = confidences

                    engine = BacktestEngine(config=trading_config, fee_rate=fee_rate)
                    bt_result = engine.run(df_feat_bt, signals_bt, confidences_bt)

                    period_text = f"{df_feat_bt.index[0].strftime('%Y-%m-%d %H:%M')} ถึง {df_feat_bt.index[-1].strftime('%Y-%m-%d %H:%M')} (รวม {len(df_feat_bt):,} แท่ง)"

                    st.session_state['last_backtest'] = {
                        'result': bt_result,
                        'df_feat': df_feat,
                        'df_feat_bt': df_feat_bt,
                        'signals': signals,
                        'signals_bt': signals_bt,
                        'model': model,
                        'metrics': metrics,
                        'period_info': period_text
                    }
                except Exception as e:
                    st.error(f"Error executing backtest: {e}")

        if 'last_backtest' in st.session_state:
            data_pack = st.session_state['last_backtest']
            result: BacktestResult = data_pack['result']
            df_feat = data_pack['df_feat']
            df_feat_bt = data_pack.get('df_feat_bt', df_feat)
            signals_bt = data_pack.get('signals_bt', data_pack['signals'])
            model = data_pack['model']
            metrics = data_pack['metrics']
            period_info = data_pack.get('period_info', '')

            if period_info:
                st.info(f"🗓️ **ช่วงเวลาที่ทดสอบ (Backtest Period):** {period_info}")

            # Top KPI metrics
            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("Total Return", f"{result.total_return_pct:+.2f}%", delta=f"{result.total_return_pct - result.buy_hold_return_pct:+.2f}% vs B&H")
            col2.metric("Portfolio Value", f"${result.final_balance:,.2f}", delta=f"${result.final_balance - result.initial_balance:+,.2f}")
            col3.metric("Win Rate", f"{result.win_rate_pct:.1f}%", f"{result.winning_trades}W / {result.losing_trades}L")
            col4.metric("Profit Factor", f"{result.profit_factor:.2f}", f"Sharpe: {result.sharpe_ratio:.2f}")
            col5.metric("Max Drawdown", f"{result.max_drawdown_pct:.2f}%", f"{result.total_trades} Trades")

            # SMC Institutional Status Card
            st.markdown("#### 🏛️ Smart Money Concepts (SMC) Current State")
            latest_bar = df_feat_bt.iloc[-1]
            smc_c1, smc_c2, smc_c3, smc_c4 = st.columns(4)

            struct_text = "🟢 BULLISH" if latest_bar.get('smc_structure', 1) == 1 else "🔴 BEARISH"
            smc_c1.metric("Market Structure", struct_text, "BOS / CHoCH Trend")

            range_pct = latest_bar.get('range_position', 0.5) * 100
            zone_text = f"🟢 DISCOUNT ({range_pct:.1f}%)" if range_pct < 50 else f"🔴 PREMIUM ({range_pct:.1f}%)"
            smc_c2.metric("Dealing Range", zone_text, "Equilibrium 50%")

            in_ob = "YES (Bullish OB)" if latest_bar.get('in_bullish_ob', False) else ("YES (Bearish OB)" if latest_bar.get('in_bearish_ob', False) else "NO")
            smc_c3.metric("Order Block (OB) Retest", in_ob)

            has_fvg = "Bullish FVG" if latest_bar.get('fvg_bullish', False) else ("Bearish FVG" if latest_bar.get('fvg_bearish', False) else "None")
            smc_c4.metric("Active Fair Value Gap", has_fvg)

            # Generate Real-time Trade Setup (Entry, SL, TP1, TP2)
            setup_gen = TradeSetupGenerator(config=trading_config)
            trade_setup = setup_gen.generate_setup(
                selected_asset,
                selected_tf,
                df_feat_bt,
                model,
                capital=initial_capital,
                risk_pct=risk_pct
            )

            # Trade Setup Display Box
            st.markdown("---")
            st.markdown("### 🎯 Real-time AI Trade Setup Card (แผนตำแหน่งเข้าเทรดล่าสุด)")

            badge_color = "#00e676" if "BUY" in trade_setup.direction else ("#ff1744" if "SELL" in trade_setup.direction else "#ffb300")
            st.markdown(f"**สัญญาณตลาด:** <span style='background-color:{badge_color}; color:#000; padding:4px 14px; border-radius:12px; font-weight:bold;'>{trade_setup.direction}</span> &nbsp;|&nbsp; AI Confidence: **{trade_setup.ai_confidence:.1%}** &nbsp;|&nbsp; Confluence Score: **{trade_setup.confluence_score}/{trade_setup.total_confluences}**", unsafe_allow_html=True)

            if trade_setup.status == "ACTIVE_SETUP":
                sc1, sc2, sc3, sc4 = st.columns(4)
                sc1.metric("🎯 ENTRY PRICE", f"${trade_setup.entry_price:,.2f}", trade_setup.entry_type)
                sc2.metric("🛑 STOP LOSS (SL)", f"${trade_setup.stop_loss:,.2f}", f"-${trade_setup.sl_distance:.2f} (-{trade_setup.sl_pct:.2f}%)")
                sc3.metric("🏆 TAKE PROFIT 1 (1:2)", f"${trade_setup.take_profit_1:,.2f}", f"+${trade_setup.tp1_distance:.2f} (+{trade_setup.tp1_pct:.2f}%)")
                sc4.metric("🚀 TAKE PROFIT 2 (1:3)", f"${trade_setup.take_profit_2:,.2f}", f"+${trade_setup.tp2_distance:.2f} (+{trade_setup.tp2_pct:.2f}%)")

                pos_c1, pos_c2, pos_c3 = st.columns(3)
                pos_c1.info(f"💼 **ขนาดออเดอร์ที่แนะนำ:** `{trade_setup.recommended_size:.4f} Units` (มูลค่า: ${trade_setup.position_value:,.2f})")
                pos_c2.info(f"🛡️ **ความเสี่ยงสูงสุด:** `${trade_setup.risk_amount:,.2f}` ({risk_pct*100:.1f}% ของพอร์ต ${initial_capital:,.2f})")
                pos_c3.info(f"📌 **เหตุผล SL:** {trade_setup.sl_reason}")
            else:
                st.warning("⚠️ **สภาวะปัจจุบัน:** ตลาดยังไม่มี Setup ที่มี Confluence สมบูรณ์ AI แนะนำให้อยู่ในสถานะ **WAIT (ถือเงินสด)** เพื่อรอจังหวะ Re-test โซนสถาบันที่ได้เปรียบ")

            with st.expander("🔍 ตรวจสอบ SMC Confluence Checklist & บทวิเคราะห์ AI"):
                for conf in trade_setup.confluence_list:
                    icon = "✅" if conf['passed'] else "❌"
                    st.write(f"{icon} **{conf['name']}**: {conf['detail']}")
                st.info(f"**AI Rationale:** {trade_setup.rationale_th}")

            # Candlestick & Signals Chart
            st.markdown("### 📈 Price Action, SMC Levels & AI Signals")
            fig_candle = plot_price_and_signals(
                df_feat_bt,
                signals=signals_bt,
                trades_df=result.trades_df,
                trade_setup=trade_setup,
                title=f"{selected_asset} ({selected_tf}) - Candlestick, SMC Levels, Entry/SL/TP & AI Trades"
            )
            st.plotly_chart(fig_candle, use_container_width=True)

            # Equity Curve & Drawdown Chart
            col_eq, col_imp = st.columns([3, 2])
            with col_eq:
                st.markdown("### 💰 Portfolio Equity Curve vs Buy & Hold")
                fig_equity = plot_equity_curve(result.equity_curve, initial_balance=result.initial_balance)
                st.plotly_chart(fig_equity, use_container_width=True)

            with col_imp:
                st.markdown("### 🧠 AI Feature Importance")
                imp_df = model.get_feature_importance()
                if not imp_df.empty:
                    fig_imp = plot_feature_importance(imp_df, top_n=10)
                    st.plotly_chart(fig_imp, use_container_width=True)
                else:
                    st.info("Feature importance not available for this model type.")

            # Trade Log
            st.markdown("### 📋 Executed Trades History")
            if not result.trades_df.empty:
                display_cols = ['entry_time', 'exit_time', 'side', 'entry_price', 'exit_price', 'size', 'pnl', 'pnl_pct', 'exit_reason']
                st.dataframe(result.trades_df[display_cols].sort_values('entry_time', ascending=False), use_container_width=True)
            else:
                st.info("No trades executed within the period under current risk and confidence parameters.")

    # TAB 2: LIVE PAPER TRADING
    with tab_paper:
        st.markdown(f"### 🟢 Real-time Paper Trading Simulator: **{selected_asset}**")
        st.write("Simulate live order execution with virtual portfolio capital without risking real money.")

        model_path = get_model_path(selected_asset, selected_tf)
        model = None
        if model_path.exists():
            model = AITradingModel.load(model_path)
            model.confidence_threshold = conf_thresh
        else:
            st.warning("⚠️ No trained model found for this asset. Please click **Train & Run Backtest** in the first tab to initialize the AI model.")

        trader = PaperTrader(
            asset_name=selected_asset,
            timeframe=selected_tf,
            model=model,
            config=trading_config
        )

        col_act1, col_act2, col_act3 = st.columns([1, 1, 2])
        with col_act1:
            step_btn = st.button("⚡ Evaluate Market (1 Step)", type="primary", use_container_width=True)
        with col_act2:
            reset_btn = st.button("🔄 Reset Portfolio", use_container_width=True)

        if reset_btn:
            trader.reset_portfolio()
            st.success("Paper trading portfolio reset to initial balance.")
            st.rerun()

        if step_btn:
            with st.spinner("Fetching latest live candle and evaluating AI decision..."):
                step_res = trader.step()
                st.session_state['latest_paper_step'] = step_res

        # Display current paper trade portfolio state
        pos = trader.open_position
        has_pos = pos is not None

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Virtual Cash", f"${trader.cash:,.2f}")
        total_eq = trader.cash + (pos['order_value'] if has_pos else 0.0)
        c2.metric("Total Equity", f"${total_eq:,.2f}")
        c3.metric("Position Status", "IN POSITION" if has_pos else "FLAT (CASH)")
        c4.metric("Closed Trades", len(trader.trade_history))

        # Show latest step if available
        if 'latest_paper_step' in st.session_state:
            step_res = st.session_state['latest_paper_step']
            st.markdown("---")
            st.markdown("#### 📡 Latest Market Evaluation")
            col_l1, col_l2, col_l3 = st.columns(3)
            with col_l1:
                st.write(f"**Timestamp:** `{step_res.get('timestamp')}`")
                st.write(f"**Latest Price:** `${step_res.get('price'):,.2f}`")
            with col_l2:
                sig = step_res.get('ai_signal', 'HOLD')
                conf = step_res.get('confidence', 0.0)
                badge_class = "status-badge-buy" if sig == "BUY" else ("status-badge-sell" if sig == "SELL" else "status-badge-hold")
                st.markdown(f"**AI Signal:** <span class='{badge_class}'>{sig} ({conf:.1%})</span>", unsafe_allow_html=True)
                st.write(f"**Action Taken:** `{step_res.get('action_taken')}`")
            with col_l3:
                probs = step_res.get('probabilities', {})
                st.write("**AI Probabilities:**")
                st.progress(probs.get('BUY', 0.0), text=f"BUY: {probs.get('BUY', 0.0):.1%}")
                st.progress(probs.get('HOLD', 0.0), text=f"HOLD: {probs.get('HOLD', 0.0):.1%}")
                st.progress(probs.get('SELL', 0.0), text=f"SELL: {probs.get('SELL', 0.0):.1%}")

            if step_res.get('action_detail'):
                st.info(step_res['action_detail'])

        # Show Open Position details
        if has_pos:
            st.markdown("---")
            st.markdown("#### 🎯 Active Open Position")
            st.json(pos)

        # Show Paper Trade History
        st.markdown("---")
        st.markdown("#### 📜 Paper Trading History")
        if trader.trade_history:
            df_hist = pd.DataFrame(trader.trade_history)
            st.dataframe(df_hist.iloc[::-1], use_container_width=True)
        else:
            st.info("No closed paper trades yet. Trigger steps to let the AI trade live market signals.")

    # TAB 3: CONTINUAL LEARNING & FEEDBACK
    with tab_learn:
        st.markdown(f"### 🧠 AI Continual Learning & Feedback: **{selected_asset}**")
        st.write("ระบบเรียนรู้แบบต่อเนื่อง (Continual / Online Learning): AI สามารถเรียนรู้เพิ่มจากข้อมูลราคาล่าสุดและประวัติการแพ้ชนะของออเดอร์ในอดีต เพื่อปรับจูนตัวเองให้เข้ากับสภาวะตลาด (Market Regime)")

        learner = ContinuousLearner(
            asset_name=selected_asset,
            timeframe=selected_tf,
            base_confidence=conf_thresh
        )
        summary = learner.get_learning_summary()

        # Learning KPIs
        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Model Generation", f"v{summary['model_version']}")
        k2.metric("Retrain Cycles", summary['total_retrain_cycles'])
        k3.metric("Experience Buffer", f"{summary['total_experiences']} Trades")
        k4.metric("Recent Win Rate", f"{summary['recent_win_rate_pct']:.1f}%", f"{summary['win_count']}W / {summary['loss_count']}L")
        adapt_conf = summary['adaptive_confidence']
        k5.metric("Adaptive Confidence", f"{adapt_conf:.1%}", delta=f"{adapt_conf - conf_thresh:+.1%} vs Base")

        st.markdown("---")
        # Retrain Action Button
        btn_col, info_col = st.columns([1, 2])
        with btn_col:
            trigger_retrain = st.button("⚡ Retrain AI on Fresh Market Data", type="primary", use_container_width=True)
        with info_col:
            st.caption("ดึงข้อมูลแท่งเทียนล่าสุด 1,500 แท่ง วิเคราะห์ SMC และใช้ Exponential Recency Weighting ให้น้ำหนักพฤติกรรมตลาดล่าสุดเป็นพิเศษ")

        if trigger_retrain:
            with st.spinner("Executing walk-forward continual learning cycle..."):
                try:
                    model_path = get_model_path(selected_asset, selected_tf)
                    if model_path.exists():
                        cur_model = AITradingModel.load(model_path)
                    else:
                        cur_model = AITradingModel(model_type=model_type, confidence_threshold=conf_thresh)

                    updated_model, metrics = learner.retrain_model_continual(cur_model, limit_candles=1500)
                    st.success(f"🎉 AI อัปเกรดเป็นเวอร์ชัน **v{updated_model.metadata.get('version', 2)}** เรียบร้อย! Out-of-sample Test Accuracy: **{metrics.accuracy:.2%}**")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error during continual learning: {e}")

        # Experience Replay Buffer Table
        st.markdown("---")
        st.markdown("#### 📦 Trade Outcome Feedback (Experience Replay Buffer)")
        st.caption("ข้อมูลผลลัพธ์ของแต่ละออเดอร์ที่ถูกบันทึกเข้าหน่วยความจำ เพื่อให้ AI นำไปประเมินความเสี่ยงและปรับความมั่นใจ (Adaptive Confidence) อัตโนมัติ")
        if learner.experiences:
            df_exp = pd.DataFrame(learner.experiences)
            disp_exp_cols = ['trade_id', 'entry_time', 'exit_time', 'entry_price', 'exit_price', 'pnl', 'pnl_pct', 'is_win', 'exit_reason', 'confidence_at_entry']
            available_exp_cols = [c for c in disp_exp_cols if c in df_exp.columns]
            st.dataframe(df_exp[available_exp_cols].iloc[::-1], use_container_width=True)
        else:
            st.info("ยังไม่มีข้อมูล Trade Experience ใน Buffer (ระบบจะบันทึกอัตโนมัติเมื่อมีการปิดออเดอร์ใน Paper Trading)")

        # Continuous Learning History Log
        st.markdown("---")
        st.markdown("#### 📈 AI Model Version Progression History")
        if learner.learning_history:
            df_hist = pd.DataFrame(learner.learning_history)
            st.dataframe(df_hist.iloc[::-1], use_container_width=True)
        else:
            st.info("โมเดลยังอยู่ในเวอร์ชันเริ่มต้น (v1)")

    # TAB 4: 24/7 ALERTS & NOTIFICATIONS
    with tab_alert:
        st.markdown("### 🔔 ระบบติดตามกราฟ 24/7 และแจ้งเตือนอัตโนมัติ (Live Alerts)")
        st.write("ระบบสามารถรันเฝ้ากราฟในพื้นหลังตลอด 24 ชั่วโมง และส่งสัญญาณแจ้งเตือนเข้ามือถือผ่าน **Telegram**, **LINE**, **Discord** หรือบนหน้าจอ **macOS** ทันทีที่มีสัญญาณเข้าเทรด หรือเมื่อออเดอร์ชน Take-Profit / Stop-Loss!")

        notifier = AlertNotifier()

        st.markdown("#### ⚙️ ตั้งค่าช่องทางการแจ้งเตือน")
        col_chan1, col_chan2 = st.columns(2)

        with col_chan1:
            st.markdown("##### 🍎 แจ้งเตือนบนเครื่อง Mac (macOS Native)")
            mac_on = st.checkbox("เปิดการแจ้งเตือนเสียงและแบนเนอร์บน macOS", value=notifier.config.get("macos_enabled", True))

            st.markdown("##### 📱 แจ้งเตือนผ่าน Telegram (แนะนำ 👍)")
            tg_on = st.checkbox("เปิดการแจ้งเตือน Telegram Bot", value=notifier.config.get("telegram_enabled", False))
            tg_token = st.text_input("Telegram Bot Token", value=notifier.config.get("telegram_token", ""), type="password", help="เช่น 123456789:ABCdefGhI...")
            tg_chat = st.text_input("Telegram Chat ID", value=notifier.config.get("telegram_chat_id", ""), help="เช่น 987654321 หรือ ID กลุ่ม")

            with st.expander("📖 วิธีสมัคร Telegram Bot ฟรีใน 1 นาที"):
                st.markdown("""
                1. เปิดแอป Telegram ค้นหาบัญชี **`@BotFather`** แล้วกด Start
                2. พิมพ์คำสั่ง `/newbot` แล้วตั้งชื่อบอทของคุณ -> คุณจะได้รับ **Bot Token**
                3. ค้นหาบัญชี **`@userinfobot`** บน Telegram แล้วกด Start -> คุณจะได้รับ **Chat ID** ของคุณ
                4. นำ Token และ Chat ID มาวางที่ช่องด้านบน แล้วกดบันทึก!
                """)

        with col_chan2:
            st.markdown("##### 💬 แจ้งเตือนผ่าน Discord")
            dc_on = st.checkbox("เปิดการแจ้งเตือน Discord Webhook", value=notifier.config.get("discord_enabled", False))
            dc_url = st.text_input("Discord Webhook URL", value=notifier.config.get("discord_webhook_url", ""), type="password")

            st.markdown("##### 🟢 แจ้งเตือนผ่าน LINE Notify")
            line_on = st.checkbox("เปิดการแจ้งเตือน LINE Notify", value=notifier.config.get("line_enabled", False))
            line_token = st.text_input("LINE Notify Token", value=notifier.config.get("line_token", ""), type="password")

        col_save, col_test = st.columns([1, 1])
        with col_save:
            if st.button("💾 บันทึกการตั้งค่าการแจ้งเตือน", type="primary", use_container_width=True):
                notifier.config.update({
                    "macos_enabled": mac_on,
                    "telegram_enabled": tg_on,
                    "telegram_token": tg_token,
                    "telegram_chat_id": tg_chat,
                    "discord_enabled": dc_on,
                    "discord_webhook_url": dc_url,
                    "line_enabled": line_on,
                    "line_token": line_token
                })
                notifier.save_config()
                st.success("บันทึกการตั้งค่าเรียบร้อยแล้ว!")

        with col_test:
            if st.button("🧪 ทดสอบส่งการแจ้งเตือน (Test Alert)", use_container_width=True):
                notifier.config.update({
                    "macos_enabled": mac_on,
                    "telegram_enabled": tg_on,
                    "telegram_token": tg_token,
                    "telegram_chat_id": tg_chat,
                    "discord_enabled": dc_on,
                    "discord_webhook_url": dc_url,
                    "line_enabled": line_on,
                    "line_token": line_token
                })
                with st.spinner("กำลังทดสอบส่งแจ้งเตือน..."):
                    test_res = notifier.test_alert()
                    st.json(test_res)

        st.markdown("---")
        st.markdown("#### 🛰️ ตั้งค่าสินทรัพย์ & Timeframe ที่ให้บอทเฝ้ากราฟ 24/7")

        mon_cfg_file = DATA_DIR / "monitor_config.json"
        def_assets = ["GOLD (XAU/USD)", "BTC/USDT", "ETH/USDT"]
        def_tfs = ["15m", "1h"]
        if mon_cfg_file.exists():
            try:
                with open(mon_cfg_file, "r") as f:
                    _c = json.load(f)
                    def_assets = _c.get("assets", def_assets)
                    def_tfs = _c.get("timeframes", def_tfs)
            except Exception:
                pass

        col_m_asset, col_m_tf = st.columns([3, 2])
        with col_m_asset:
            selected_mon_assets = st.multiselect(
                "เลือกสินทรัพย์ที่ต้องการให้บอทเฝ้าติดตาม:",
                options=list(SUPPORTED_ASSETS.keys()),
                default=def_assets
            )
        with col_m_tf:
            selected_mon_tfs = st.multiselect(
                "เลือก Timeframe ที่ต้องการจับสัญญาณ:",
                options=SUPPORTED_TIMEFRAMES,
                default=def_tfs,
                help="เลือกได้อิสระตามต้องการ เช่น 15m สำหรับ Scalp หรือ 1h/4h สำหรับ Swing"
            )

        col_m_save, col_m_scan = st.columns([1, 1])
        with col_m_save:
            if st.button("💾 บันทึกการตั้งค่าเฝ้าตลาด 24/7", type="primary", use_container_width=True):
                if not selected_mon_tfs:
                    st.error("กรุณาเลือกอย่างน้อย 1 Timeframe")
                elif not selected_mon_assets:
                    st.error("กรุณาเลือกอย่างน้อย 1 สินทรัพย์")
                else:
                    with open(mon_cfg_file, "w") as f:
                        json.dump({
                            "assets": selected_mon_assets,
                            "timeframes": selected_mon_tfs,
                            "interval": 60
                        }, f, indent=2)
                    st.success("บันทึกเรียบร้อย! ตัว Monitor 24/7 ใน Background จะอัปเดต Timeframe ใหม่ให้อัตโนมัติทันที")

        with col_m_scan:
            run_scan = st.button("⚡ ตรวจจับสัญญาณตลาดสดเดี๋ยวนี้ (Scan Markets)", use_container_width=True)

        if run_scan and selected_mon_assets and selected_mon_tfs:
            with st.spinner("กำลังสแกนตลาดและวิเคราะห์สัญญาณสด..."):
                monitor = LiveMarketMonitor(assets=selected_mon_assets, timeframes=selected_mon_tfs)
                scan_results = monitor.run_single_pass()
                st.success(f"สแกนเสร็จสิ้นเรียบร้อย! ตรวจสอบ {len(scan_results)} รายการ")
                df_scan = pd.DataFrame(scan_results)
                disp_scan_cols = ['asset', 'timeframe', 'price', 'signal', 'confidence', 'confluence_score', 'alert_sent']
                avail_scan = [c for c in disp_scan_cols if c in df_scan.columns]
                st.dataframe(df_scan[avail_scan], use_container_width=True)

        st.caption("💡 **วิธีเปิดให้บอทเฝ้ากราฟ 24/7 ใน Background:** ตัวบอทจะอ่านการตั้งค่าด้านบนนี้ไปใช้อัตโนมัติ โดยไม่ต้องแก้ไขโค้ดใดๆ เพิ่มเติมครับ")

    # TAB 5: MARKET INDICATORS & RAW DATA
    with tab_data:
        st.markdown(f"### 🔍 Technical Indicators & Feature Matrix: **{selected_asset}**")
        loader = MarketDataLoader()
        df_raw = loader.fetch_data(selected_asset, timeframe=selected_tf, limit=200)
        fe = FeatureEngineer()
        df_ind, _ = fe.prepare_features(df_raw, include_target=False)

        latest = df_ind.iloc[-1]
        col_t1, col_t2, col_t3, col_t4 = st.columns(4)
        col_t1.metric("RSI (14)", f"{latest['rsi']:.1f}", "Overbought > 70 / Oversold < 30")
        col_t2.metric("MACD Hist", f"{latest['macd_hist']:.4f}", "Bullish > 0" if latest['macd_hist'] > 0 else "Bearish < 0")
        col_t3.metric("ATR Volatility", f"${latest['atr']:.2f}", f"{latest['atr_pct']*100:.2f}% of price")
        trend_status = "BULLISH (EMA21 > EMA50)" if latest['ema_trend'] == 1 else "BEARISH (EMA21 < EMA50)"
        col_t4.metric("Trend State", trend_status)

        st.markdown("#### Latest 50 Bars with Technical Indicators")
        st.dataframe(df_ind.tail(50), use_container_width=True)


if __name__ == "__main__":
    main()
