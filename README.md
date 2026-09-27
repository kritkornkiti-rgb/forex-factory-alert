# 🤖 AI bottrade - Autonomous AI Trading System

**AI bottrade** คือระบบบอทเทรดอัจฉริยะที่ผสมผสาน **Technical Analysis (การวิเคราะห์ทางเทคนิค)** ร่วมกับ **Machine Learning (AI คาดการณ์ทิศทางราคา)** สำหรับการเทรดทั้งในตลาด **Cryptocurrency** และ **โลหะมีค่าทุกประเภท (Precious Metals)** พร้อมระบบ **Backtesting** และ **Paper Trading** จำลองการเทรดสดแบบเสมือนจริงโดยไม่ต้องเสี่ยงเงินทุน

---

## 🌟 จุดเด่นของระบบ (Key Features)

1. **รองรับสินทรัพย์หลากหลาย (Multi-Asset Support)**:
   - **Precious Metals**: ทองคำ (Gold XAU/USD: `GC=F`), เงิน (Silver XAG/USD: `SI=F`), แพลทินัม (Platinum: `PL=F`), แพลเลเดียม (Palladium: `PA=F`)
   - **Crypto Pairs**: Bitcoin (`BTC/USDT`), Ethereum (`ETH/USDT`), Solana (`SOL/USDT`), Binance Coin (`BNB/USDT`), Ripple (`XRP/USDT`)
   - เชื่อมต่อข้อมูลอัตโนมัติจาก **Binance (ผ่าน CCXT)** และ **Yahoo Finance** พร้อมระบบ Cache อัจฉริยะ

2. **สถาปัตยกรรม Smart Money Concepts (SMC Engine)**:
   - **Market Structure**: ตรวจจับ **BOS (Break of Structure)** ยืนยันทิศทางเทรนด์ และ **CHoCH (Change of Character)** จับสัญญาณกลับตัวของรายใหญ่
   - **Order Blocks (OB)**: ระบุ Bullish Order Block (โซนสถาบันเข้าซื้อสะสม) และ Bearish Order Block (โซนสถาบันเทขาย) พร้อมระบบตรวจสอบการ Re-test / Mitigation
   - **Fair Value Gaps (FVG)**: คำนวณ Imbalance / ช่องว่างราคาที่รายใหญ่ทิ้งไว้ เพื่อดักจังหวะราคากลับมา Rebalance
   - **Liquidity Sweeps**: ตรวจจับการกวาดสภาพคล่อง (Run on Liquidity / Fakeout) ทั้ง Buy-Side (BSL) และ Sell-Side (SSL)
   - **Premium vs. Discount Equilibrium**: คำนวณเส้นกึ่งกลาง 50% ของ Dealing Range เพื่อซื้อในโซนถูก (Discount) และขายในโซนแพง (Premium)

3. **การวิเคราะห์สัญญาณเทคนิคเต็มรูปแบบ (Technical Analysis Engine)**:
   - **Trend**: EMA (9, 21, 50, 200), EMA Distance & Trend Ratio
   - **Momentum**: RSI (14 & 7), Stochastic Oscillator (%K, %D), MACD (Line, Signal, Histogram)
   - **Volatility**: Bollinger Bands (Upper, Middle, Lower, Bandwidth, %B), ATR (Average True Range)
   - **Volume & Direction**: On-Balance Volume (OBV), Volume SMA Ratio, ADX (+DI, -DI)

4. **โมเดล AI / Machine Learning (Predictive Engine)**:
   - ผสานฟีเจอร์จากทั้ง **SMC (Institutional Logic)** + **Technical Indicators**
   - ใช้อัลกอริทึม **Histogram Gradient Boosting** และ **Random Forest**
   - วิเคราะห์ TimeSeriesSplit ป้องกันปัญหา Data Leakage (ไม่มี Lookahead Bias)
   - มีระบบ **Confidence Thresholding** (บอทจะออกคำสั่งเทรดเฉพาะเมื่อ AI มีความมั่นใจเกินเกณฑ์ เช่น > 52-55%)
   - สกัด Feature Importance แสดงว่าปัจจัยและ Indicator ใดมีอิทธิพลต่อการตัดสินใจของ AI มากที่สุด

5. **ระบบการเรียนรู้แบบต่อเนื่องและปรับตัวตามสภาวะตลาด (Continuous Learning Engine)**:
   - **Walk-Forward Retraining**: ป้องกันโมเดลหมดอายุ (Concept Drift / Market Decay) โดยสามารถดึงข้อมูลแท่งเทียนใหม่ล่าสุดมาเทรนต่อยอดได้เสมอ
   - **Exponential Recency Weighting**: ให้น้ำหนักความสำคัญกับพฤติกรรมราคาและโครงสร้าง SMC ล่าสุดมากกว่าข้อมูลในอดีตไกลๆ
   - **Experience Replay Buffer**: จดจำประวัติและผลลัพธ์ของแต่ละออเดอร์ (Win / Loss, Profit, Stop-Loss Hit) เพื่อนำมาเป็น Feedback ให้ AI
   - **Adaptive Confidence Thresholding**: ปรับความเข้มงวดในการออกออเดอร์อัตโนมัติ (เช่น ถ้าตลาดผันผวนไซด์เวย์จน Win Rate ลด AI จะเพิ่มเกณฑ์ความมั่นใจขึ้นอัตโนมัติ เพื่อเลี่ยงการเทรดที่เสี่ยง)
   - **Model Generation Tracking**: ติดตามการอัปเกรดเวอร์ชันของโมเดล (`v1 -> v2 -> v3...`) พร้อมประวัติความแม่นยำในแต่ละรอบ

6. **การบริหารความเสี่ยงระดับมืออาชีพ (Risk Management)**:
   - **Dynamic Stop-Loss**: คำนวณตามความผันผวนจริงของตลาดด้วย `ATR x Multiplier` (ค่าเริ่มต้น 1.5x ATR) หรือระดับ Invalidation ของ Order Block
   - **Dynamic Take-Profit**: อัตราส่วน Risk:Reward เฉลี่ย 1:1.67+ ด้วย `ATR x Multiplier` (ค่าเริ่มต้น 2.5x ATR)
   - **Position Sizing**: จำกัดความเสี่ยงไม่เกิน 2% ของเงินทุนรวมต่อการเทรด 1 ครั้ง (Capital Risk Sizing)
   - คำนวณค่าธรรมเนียมจริง (Exchange Fees) และ Slippage ในทุกออเดอร์

7. **ระบบทดสอบและจำลองเทรดสด (Backtesting & Paper Trading)**:
   - **Backtesting Engine**: วิเคราะห์ผลงานย้อนหลังอย่างละเอียด (Total Return, Win Rate, Profit Factor, Sharpe Ratio, Max Drawdown, Equity Curve)
   - **Live Paper Trading Simulator**: ระบบจำลองเทรดสดตามราคาตลาดจริงแบบ Real-time บันทึกประวัติและพอร์ตโฟลิโอลงใน Local Database

8. **ระบบติดตามกราฟ 24/7 และแจ้งเตือนอัตโนมัติ (Live 24/7 Alert Engine)**:
   - **Multi-Asset Background Watcher**: เฝ้ากราฟทั้งทองคำ (Gold) และคริปโต (BTC, ETH, SOL) ตลอด 24 ชั่วโมง
   - **Telegram Bot Instant Push**: ส่งสัญญาณเตือนเข้ามือถือทันที (พร้อมราคา Entry, SL, TP1, TP2, ขนาดไม้ และเหตุผล SMC)
   - **macOS Native Banner & Sound**: ส่งเสียงเตือนและแสดงป้ายแจ้งเตือนบนหน้าจอ Mac ทันทีโดยไม่ต้องต่อเน็ตเวิร์กภายนอก
   - **Discord Webhook & LINE Notify**: รองรับการส่งสัญญาณเข้าห้องแชท Discord และกลุ่ม LINE
   - **Anti-Spam Cooldown**: ระบบป้องกันการส่งเตือนซ้ำในแท่งเทียนเดิม

9. **Web Dashboard สวยงามใช้งานง่าย (Streamlit + Plotly)**:
   - หน้าจอกราฟแท่งเทียน Candlestick อินเตอร์แอคทีฟ พร้อมเส้นระดับราคา Entry, SL, TP1, TP2
   - แสดงสัญลักษณ์ **BOS**, **CHoCH**, จุดเข้าซื้อตาม SMC, จุดทำกำไร (TP), จุดตัดขาดทุน (SL)
   - แท็บ **Continual Learning**: แสดง Generation ของโมเดล, Experience Buffer, และปุ่มกดให้ AI เรียนรู้ต่อจากข้อมูลแท่งเทียนสดได้ทันที
   - แท็บ **24/7 Alerts & Notifications**: จัดการ Token การแจ้งเตือน และสั่งสแกนตลาดสดได้ทันที

---

## 📁 โครงสร้างโปรเจกต์ (Project Structure)

```
AI bottrade/
├── .venv/                     # Virtual Environment Python
├── data/                      # แคชข้อมูลราคาและประวัติ Paper Trading
├── models_saved/              # โมเดล AI ที่เทรนแล้ว (.joblib)
├── src/
│   ├── config.py              # การตั้งค่าสินทรัพย์และตัวแปรระบบ
│   ├── data_loader.py         # ระบบดึงข้อมูลจาก CCXT และ Yahoo Finance
│   ├── smc.py                 # Smart Money Concepts Engine (BOS, CHoCH, OB, FVG, Sweeps, Premium/Discount)
│   ├── indicators.py          # คำนวณ Indicators เชิงเทคนิค (Vectorized Pandas/Numpy)
│   ├── feature_engineering.py # สกัด SMC + Technical Features และสร้าง Target Labels
│   ├── model.py               # โมเดล Machine Learning, Cross-validation & Predictor
│   ├── trade_setup.py         # คำนวณแผนเข้าเทรด Entry, SL, TP1, TP2, R:R และ Position Sizing
│   ├── continuous_learning.py # ระบบเรียนรู้ต่อเนื่อง, Experience Buffer & Adaptive Confidence
│   ├── notifier.py            # ตัวส่งสัญญาณแจ้งเตือนผ่าน macOS, Telegram, Discord, LINE
│   ├── live_monitor.py        # ลูปเฝ้ากราฟ 24/7 และตรวจจับสัญญาณอัตโนมัติ
│   ├── backtester.py          # ระบบจำลองเทรดย้อนหลังพร้อมคำนวณ Fees/Slippage
│   ├── paper_trader.py        # เอนจินจำลองเทรดสดพร้อมจัดการกระเป๋าเงินเสมือน
│   └── utils.py               # สร้างชาร์ตกราฟ Plotly Interactive พร้อมเลเยอร์ SMC
├── app.py                     # Web Dashboard (Streamlit)
├── main.py                    # โปรแกรมสั่งการผ่าน Command Line (CLI)
├── start.command              # ดับเบิลคลิกเพื่อเปิด Web Dashboard บน Mac ทันที
├── monitor_24_7.command       # ดับเบิลคลิกเพื่อเริ่มเฝ้ากราฟ 24/7 และส่งแจ้งเตือนทันที
├── requirements.txt           # รายการ Dependencies
└── README.md                  # คู่มือการใช้งาน
```

---

## 🚀 วิธีการติดตั้งและใช้งาน (Quick Start)

### 1. เข้าสู่โฟลเดอร์และเปิดใช้งาน Virtual Environment
```bash
cd "/Users/kritsmacbook/Desktop/AI bottrade"
source .venv/bin/activate
```

### 2. รันหน้าต่าง Web Dashboard (แนะนำ 👍)
```bash
.venv/bin/streamlit run app.py
```
เมื่อรันคำสั่ง ระบบจะเปิดหน้าต่างเบราว์เซอร์อัตโนมัติที่ `http://localhost:8501`
- คุณสามารถเลือกคู่เหรียญคริปโต หรือทองคำ/เงิน
- กดปุ่ม **🚀 Train & Run Backtest** เพื่อให้ AI เทรนโมเดลและแสดงผลลัพธ์
- เข้าแท็บ **🟢 Live Paper Trading** เพื่อทดลองรันบอทเทรดกับราคาตลาดจริง

---

## 💻 การสั่งงานผ่าน Command Line (CLI)

คุณสามารถสั่งงานผ่าน Terminal ได้โดยตรงด้วยคำสั่ง `main.py`:

### ดูรายชื่อสินทรัพย์ที่รองรับ
```bash
.venv/bin/python main.py list-assets
```

### สั่งเทรนโมเดล AI (Train)
```bash
# เทรนโมเดลสำหรับทองคำ
.venv/bin/python main.py train --asset "GOLD (XAU/USD)" --timeframe 1h

# เทรนโมเดลสำหรับ Bitcoin
.venv/bin/python main.py train --asset "BTC/USDT" --timeframe 1h
```

### คำนวณแผนและตำแหน่งเข้าเทรดสดแบบละเอียด (Trade Setup Card)
```bash
# วิเคราะห์ตำแหน่ง Entry, Stop Loss, Take Profit 1, Take Profit 2 และ Lot Size ทองคำ
.venv/bin/python main.py setup --asset "GOLD (XAU/USD)" --timeframe 1h

# วิเคราะห์ตำแหน่งเข้าเทรด Bitcoin พร้อมคำนวณขนาดไม้ตามทุน $10,000 และความเสี่ยง 2%
.venv/bin/python main.py setup --asset "BTC/USDT" --timeframe 1h --capital 10000 --risk 0.02
```

### สั่งให้ AI เรียนรู้เพิ่มต่อเนื่องจากข้อมูลล่าสุด (Continual Learning)
```bash
# อัปเกรดโมเดล AI ด้วยข้อมูลแท่งเทียนสดล่าสุดและน้ำหนักตามพฤติกรรมตลาดใหม่
.venv/bin/python main.py continual-learn --asset "GOLD (XAU/USD)" --timeframe 1h
```

### ทดสอบกลยุทธ์ย้อนหลัง (Backtest)
```bash
# ทดสอบ Backtest ทองคำ
.venv/bin/python main.py backtest --asset "GOLD (XAU/USD)" --timeframe 1h

# ทดสอบ Backtest Bitcoin พร้อมกำหนดความเสี่ยง 2%
.venv/bin/python main.py backtest --asset "BTC/USDT" --timeframe 1h --risk 0.02
```

### จำลองเทรดสด (Paper Trading)
```bash
# ทดสอบตรวจจับสัญญาณตลาด 1 ครั้ง (Single Step)
.venv/bin/python main.py paper-trade --asset "GOLD (XAU/USD)" --timeframe 1h --once

# รันต่อเนื่องตรวจจับสัญญาณทุก 60 วินาที
.venv/bin/python main.py paper-trade --asset "BTC/USDT" --timeframe 1h --interval 60
```

### เริ่มต้นเฝ้ากราฟและส่งการแจ้งเตือน 24/7 (Live Market Monitor)
```bash
# เฝ้ากราฟทองคำและบิตคอยน์ พร้อมส่งแจ้งเตือนเข้า Telegram / macOS ทุก 60 วินาที
.venv/bin/python main.py monitor --assets "GOLD (XAU/USD)" "BTC/USDT" --interval 60
```
