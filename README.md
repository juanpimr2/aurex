# AUREX

> *"In the calculus of markets, precision and patience are the only true weapons."*

**Aurex** is an open-source algorithmic trading system for **XAUUSD (Gold)** on the [Capital.com](https://capital.com) platform. It combines a triple EMA crossover with RSI filtering, Bollinger Bands, and ATR-based position sizing to capture swing moves — primarily on daily timeframes.

Built with Python (FastAPI) on the backend and Vue 3 on the frontend, with a real-time WebSocket dashboard and a walk-forward backtester that pulls live data directly from Capital.com.

---

## Features

- **Triple EMA strategy** (8 / 21 / 50) with RSI + Bollinger Band confirmation
- **ATR-based dynamic SL/TP** — adapts to current market volatility
- **Realistic backtester** — includes spread simulation, compounding, Sharpe, max drawdown
- **Live trader** — runs in a background thread, checks signals on configurable intervals
- **FastAPI backend** — REST + WebSocket endpoints for the dashboard
- **Vue 3 dashboard** — real-time equity curve, open positions, backtest UI
- **Multi-timeframe signal analysis** — DAY / H4 / H1 alignment checks

---

## Strategy Overview

The core logic replicates a Pine Script strategy originally backtested on TradingView (+449% on XAUUSD daily, 2022–2024). The Python implementation adds realistic spread costs and walk-forward simulation.

| Parameter | Value |
|-----------|-------|
| EMA periods | 8 / 21 / 50 |
| RSI period | 14 (entry range: 35–65) |
| Bollinger Bands | 20 periods, 2.0 std dev |
| ATR Stop Loss | 1.0× ATR |
| ATR Take Profit | 2.5× ATR (R:R = 1:2.5) |
| Risk per trade | 1.5% of equity |
| Max open positions | 2 |

The original Pine Script source is available in [`docs/xauusd_original_strategy.pine`](docs/xauusd_original_strategy.pine).

---

## Project Structure

```
aurex/
├── bot-centralizado/
│   ├── backend/
│   │   ├── main.py            # FastAPI app — REST + WebSocket
│   │   ├── capital_client.py  # Capital.com API wrapper
│   │   ├── strategy.py        # EMA / RSI / ATR signal logic
│   │   ├── backtester.py      # Walk-forward backtester
│   │   ├── trader.py          # Live trading loop
│   │   ├── requirements.txt
│   │   └── .env               # ← your credentials (never committed)
│   └── frontend/
│       ├── src/
│       │   ├── views/
│       │   │   ├── Dashboard.vue   # Live P&L, positions
│       │   │   ├── Backtest.vue    # Run & visualise backtests
│       │   │   └── Settings.vue    # Bot configuration
│       │   └── stores/trading.js   # Pinia global state
│       ├── package.json
│       └── vite.config.js
├── docs/
│   └── xauusd_original_strategy.pine  # Original TradingView Pine Script
├── legacy/
│   ├── trading_bot/           # v1 standalone bot
│   └── trading-reports/       # v1 reporting scripts
├── .env.example               # ← copy this to bot-centralizado/backend/.env
└── README.md
```

---

## Setup

### 1. Get your Capital.com API key

1. Log in to [Capital.com](https://capital.com)
2. Go to **Settings → API Management**
3. Create a new API key (read + trade permissions)

### 2. Configure credentials

Copy `.env.example` to `bot-centralizado/backend/.env` and fill in your details:

```bash
cp .env.example bot-centralizado/backend/.env
```

```env
CAPITAL_API_KEY=your_api_key_here
CAPITAL_PASSWORD=your_account_password
CAPITAL_EMAIL=your@email.com
CAPITAL_MODE=DEMO          # Start with DEMO. Change to REAL when ready.
INITIAL_CAPITAL=300
RISK_PER_TRADE=1.5
MAX_POSITIONS=2
```

> **Important:** Never commit your `.env` file. It is already listed in `.gitignore`.

### 3. Install backend dependencies

```bash
cd bot-centralizado/backend
pip install -r requirements.txt
python main.py
# API running at http://localhost:8000
```

### 4. Install and run frontend

```bash
cd bot-centralizado/frontend
npm install
npm run dev
# Dashboard at http://localhost:5173
```

---

## Usage

### Run a backtest first

Before going live, validate the strategy against historical data:

1. Open the dashboard → **Backtest** tab
2. Select asset (`GOLD`), timeframe (`DAY`), capital, and date range
3. Review: Win Rate, Profit Factor, Max Drawdown, equity curve

Typical results on GOLD daily (500 candles, Sep 2024 – Apr 2026):
```
Win Rate:       ~46%
Profit Factor:  ~2.26
Return:         ~+441%
Max Drawdown:   ~27%
```

> Past performance is not indicative of future results.

### Start the live bot

Via the dashboard **Settings** tab, or directly via the API:

```bash
curl -X POST http://localhost:8000/api/start \
  -H "Content-Type: application/json" \
  -d '{
    "epic": "GOLD",
    "timeframe": "DAY",
    "risk_pct": 1.5,
    "max_positions": 2,
    "check_interval": 3600
  }'
```

### API endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/status` | Bot status + open positions |
| GET | `/api/balance` | Account balance |
| GET | `/api/positions` | Open positions |
| POST | `/api/backtest` | Run a backtest |
| POST | `/api/start` | Start live trading |
| POST | `/api/stop` | Stop live trading |
| GET | `/api/market/{epic}` | Current price + signal |
| WS | `/ws` | Real-time updates |

---

## Risk Warning

- **Always start in DEMO mode.** Verify everything works before switching to REAL.
- This software is provided as-is. Algorithmic trading carries significant financial risk.
- The strategy has a ~41–47% win rate — drawdowns are expected and can be significant.
- Never risk capital you cannot afford to lose.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, FastAPI, pandas, numpy |
| Frontend | Vue 3, Vite, Pinia, Chart.js |
| Broker API | Capital.com REST API v1 |
| Strategy | EMA / RSI / ATR / Bollinger Bands |

---

## License

MIT — free to use, modify, and distribute.
