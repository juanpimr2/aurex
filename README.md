# Aurex

> Algorithmic trading system for Capital.com — Gold · Stocks · Indices · Forex · Crypto — EMA · RSI · Bollinger Bands · ATR

> *"A warrior does not strike in haste. Precision is the virtue of the patient mind."*
> — Space Marine aphorism, Chapter unknown

Aurex is a Python + Vue 3 trading bot that captures swing moves across any instrument available on Capital.com: commodities (Gold, Oil), stock indices (SPX500, NAS100), individual stocks (NVIDIA, Apple), forex pairs (EURUSD, GBPUSD), and crypto (BTCUSD). It works in three independent modes: **market analysis only**, **backtesting**, or **live trading**. No deposit required — a free Capital.com demo account is enough.

---

## Table of Contents

- [Quick Start](#quick-start)
- [Usage Modes](#usage-modes)
  - [Mode 1 — Market Analysis (no money required)](#mode-1--market-analysis-no-money-required)
  - [Mode 2 — Backtesting](#mode-2--backtesting)
  - [Mode 3 — Live Trading](#mode-3--live-trading)
- [Configuration](#configuration)
- [Modules](#modules)
- [REST API Reference](#rest-api-reference)
- [Capital.com API](#capitalcom-api)
- [Architecture](#architecture)
- [For AI Agents](#for-ai-agents)

---

## Quick Start

```bash
# 1. Clone and configure
git clone https://github.com/juanpimr2/aurex.git && cd aurex
cp .env.example bot-centralizado/backend/.env
# → edit .env with your Capital.com credentials

# 2. Install backend
cd bot-centralizado/backend && pip install -r requirements.txt

# 3. Start API server
python main.py
# → http://localhost:8000

# 4. (Optional) Start dashboard
cd ../frontend && npm install && npm run dev
# → http://localhost:5173
```

> **Prerequisites:** Python 3.11+, Node.js 18+ (only for dashboard), Capital.com account (free demo works)

---

## Usage Modes

### Mode 1 — Market Analysis (no money required)

Get real-time signals and historical analysis for any instrument **without placing any trade**. A free Capital.com demo account gives you full API access to price history, market data, and streaming quotes.

**Get current signal for Gold:**
```bash
curl http://localhost:8000/api/market/GOLD?timeframe=DAY
```

```json
{
  "epic": "GOLD",
  "timeframe": "DAY",
  "current_price": 4754.40,
  "signal": "SELL",
  "rsi": 60.1,
  "atr": 182.23,
  "ema_fast": 4684.82,
  "ema_slow": 4711.98,
  "ema_long": 4792.99,
  "bb_upper": 5002.51,
  "bb_lower": 4274.97,
  "timestamp": "2026-04-09T17:00:00"
}
```

**Run signal analysis directly in Python:**
```python
from capital_client import CapitalClient
from strategy import StrategyConfig, calculate_indicators, generate_signals

client = CapitalClient()
client.login()

df = client.get_prices("GOLD", resolution="DAY", max_points=200)
cfg = StrategyConfig()
df = calculate_indicators(df, cfg)
df = generate_signals(df, cfg)

last = df.iloc[-2]  # last complete candle
print(f"Signal: {'BUY' if last['buy_signal'] else 'SELL' if last['sell_signal'] else 'NONE'}")
print(f"RSI: {last['rsi']:.1f} | ATR: {last['atr']:.2f}")
```

**Available instruments — `epic` reference:**

| Instrument | Epic | Category |
|------------|------|----------|
| Gold | `GOLD` | Commodity |
| Silver | `SILVER` | Commodity |
| Crude Oil (WTI) | `OIL_CRUDE` | Commodity |
| S&P 500 | `US500` | Index |
| Nasdaq 100 | `US100` | Index |
| Dow Jones | `US30` | Index |
| DAX 40 | `DE40` | Index |
| NVIDIA | `NVDA` | Stock |
| Apple | `AAPL` | Stock |
| Tesla | `TSLA` | Stock |
| EUR/USD | `EURUSD` | Forex |
| GBP/USD | `GBPUSD` | Forex |
| Bitcoin | `BTCUSD` | Crypto |
| Ethereum | `ETHUSD` | Crypto |

> **Can't find your instrument?** Use `trading-reports/find_epic.py` to search the full Capital.com catalogue by name.

**Examples:**
```bash
curl "http://localhost:8000/api/market/NVDA?timeframe=DAY"
curl "http://localhost:8000/api/market/US500?timeframe=HOUR_4"
curl "http://localhost:8000/api/market/BTCUSD?timeframe=HOUR"
```

**Supported resolutions:** `MINUTE` · `MINUTE_5` · `MINUTE_15` · `MINUTE_30` · `HOUR` · `HOUR_4` · `DAY` · `WEEK`

---

### Mode 2 — Backtesting

Run a walk-forward backtest against real historical data from Capital.com. Includes spread simulation, compounding, and full performance metrics.

**Strategy presets** (`GET /api/presets` for full list):

| Preset | Timeframe | SL | TP | Risk | Best for |
|--------|-----------|----|----|------|----------|
| `SWING` | DAY | 2× ATR | 2.5× ATR | 1.5% | Gold, indices — multi-day moves |
| `SCALP` | HOUR | 1.5× ATR | 2× ATR | 1.0% | Forex, crypto — intraday |
| `SWING_CONSERVATIVE` | DAY | 2.5× ATR | 3× ATR | 1.0% | New accounts, high-volatility instruments |

---

**Example: 500 EUR account · NVIDIA · SWING preset**
```bash
curl -X POST http://localhost:8000/api/backtest \
  -H "Content-Type: application/json" \
  -d '{
    "epic": "NVDA",
    "timeframe": "DAY",
    "initial_capital": 500,
    "preset": "SWING"
  }'
```

**Example: 500 EUR account · S&P 500 · SCALP preset**
```bash
curl -X POST http://localhost:8000/api/backtest \
  -H "Content-Type: application/json" \
  -d '{
    "epic": "US500",
    "timeframe": "HOUR",
    "initial_capital": 500,
    "preset": "SCALP"
  }'
```

**Manual parameter override (advanced):**
```bash
curl -X POST http://localhost:8000/api/backtest \
  -H "Content-Type: application/json" \
  -d '{
    "epic": "GOLD",
    "timeframe": "DAY",
    "initial_capital": 300,
    "risk_pct": 1.5,
    "spread_points": 0.5,
    "max_candles": 500,
    "ema_fast": 8, "ema_slow": 21, "ema_long": 50,
    "atr_sl_mult": 2.0, "atr_tp_mult": 2.5
  }'
```

**Expected output:**
```json
{
  "stats": {
    "total_trades": 29,
    "win_rate_pct": 46.7,
    "profit_factor": 2.26,
    "total_return_pct": 441.0,
    "final_equity": 1623.00,
    "max_drawdown_pct": 26.9,
    "avg_win_money": 186.23,
    "avg_loss_money": -70.65,
    "expectancy_per_trade": 35.65,
    "verdict": "RENTABLE - Puede usarse en live"
  },
  "date_range": {
    "start": "2024-09-02",
    "end": "2026-04-09"
  }
}
```

**Via Python directly (no server needed):**
```python
import os
os.environ["CAPITAL_MODE"] = "DEMO"

from capital_client import CapitalClient
from backtester import BacktestConfig, run_backtest
from strategy import StrategyConfig, STRATEGY_PRESETS

client = CapitalClient()
client.login()

# Example: 500 EUR on NVIDIA with SWING preset
df = client.get_prices("NVDA", "DAY", 500)
preset_params = STRATEGY_PRESETS["SWING"]["params"]

result = run_backtest(df, BacktestConfig(
    epic="NVDA",
    timeframe="DAY",
    initial_capital=500.0,
    risk_pct=1.5,
    strategy=StrategyConfig(**preset_params),
))
print(result.stats)
```

---

### Mode 3 — Live Trading

The bot runs in a background thread, checks signals at a configurable interval, and opens/closes positions automatically.

> **Always test in DEMO first.** Set `CAPITAL_MODE=DEMO` in `.env`.

**Start the bot (with preset — recommended):**
```bash
# GOLD swing trading
curl -X POST http://localhost:8000/api/start \
  -H "Content-Type: application/json" \
  -d '{"epic": "GOLD", "preset": "SWING", "risk_pct": 1.5, "max_positions": 2}'

# NVIDIA scalping
curl -X POST http://localhost:8000/api/start \
  -H "Content-Type: application/json" \
  -d '{"epic": "NVDA", "preset": "SCALP", "risk_pct": 1.0, "max_positions": 1}'
```
```json
{ "ok": true, "message": "Bot started: GOLD @ DAY (SWING)" }
```

**Start the bot (manual parameters):**
```bash
curl -X POST http://localhost:8000/api/start \
  -H "Content-Type: application/json" \
  -d '{
    "epic": "GOLD",
    "timeframe": "DAY",
    "risk_pct": 1.5,
    "max_positions": 2,
    "check_interval": 3600,
    "ema_fast": 8, "ema_slow": 21, "ema_long": 50,
    "atr_sl_mult": 2.0, "atr_tp_mult": 2.5
  }'
```

**Check status:**
```bash
curl http://localhost:8000/api/status
```

**Stop the bot:**
```bash
curl -X POST http://localhost:8000/api/stop
```

**Risk management defaults:**
| Parameter | Default | Description |
|-----------|---------|-------------|
| `risk_pct` | `1.5` | % of equity risked per trade |
| `max_positions` | `2` | Max simultaneous open positions |
| `atr_sl_mult` | `2.0` | Stop loss = ATR × multiplier (professional standard) |
| `atr_tp_mult` | `2.5` | Take profit = ATR × multiplier (R:R = 1:2.5) |
| `check_interval` | `3600` | Seconds between signal checks |
| `preset` | `null` | Strategy preset name — overrides individual params |

---

## Configuration

Copy `.env.example` to `bot-centralizado/backend/.env`:

```bash
cp .env.example bot-centralizado/backend/.env
```

| Variable | Example | Description |
|----------|---------|-------------|
| `CAPITAL_API_KEY` | `abc123xyz` | API key from Capital.com → Settings → API Management |
| `CAPITAL_PASSWORD` | `yourpassword` | Your Capital.com account password |
| `CAPITAL_EMAIL` | `you@email.com` | Your Capital.com account email |
| `CAPITAL_MODE` | `DEMO` | `DEMO` for paper trading · `REAL` for live trading |
| `INITIAL_CAPITAL` | `300` | Starting capital reference (for position sizing) |
| `RISK_PER_TRADE` | `1.5` | % of equity risked per trade |
| `MAX_POSITIONS` | `2` | Maximum open positions at once |

> **Security:** `.env` is listed in `.gitignore` and will never be committed.

---

## Modules

### `capital_client.py` — Capital.com API wrapper

Handles authentication, session management, and all API calls.

```python
from capital_client import CapitalClient

client = CapitalClient()
client.login()

# Get OHLCV price history
df = client.get_prices("GOLD", resolution="HOUR_4", max_points=200)

# Get account balance
balance = client.get_balance()
# → {"balance": 300.0, "available": 298.0, "profit_loss": 2.0}

# Get open positions
positions = client.get_positions()

# Open a position
deal_id = client.open_position(
    epic="GOLD",
    direction="BUY",       # or "SELL"
    size=1.0,
    stop_loss=4700.0,
    take_profit=4900.0,
)

# Close a position
client.close_position(deal_id)
```

---

### `strategy.py` — Signal generation

Calculates EMA / RSI / Bollinger / ATR indicators and generates BUY/SELL signals.

```python
from strategy import StrategyConfig, calculate_indicators, generate_signals, get_latest_signal

cfg = StrategyConfig(
    ema_fast=8, ema_slow=21, ema_long=50,
    rsi_period=14, rsi_overbought=65.0, rsi_oversold=35.0,
    atr_sl_mult=1.0, atr_tp_mult=2.5,
    risk_pct=1.5,
)

# Full indicator calculation
df = calculate_indicators(df, cfg)
df = generate_signals(df, cfg)

# Or get the latest actionable signal directly
signal = get_latest_signal(df, cfg)
# → {
#     "direction": "SELL",
#     "entry_price": 4715.64,
#     "stop_loss": 4897.87,
#     "take_profit": 4260.07,
#     "rsi": 60.0,
#     "atr": 182.23,
#     "timestamp": "2026-04-08 02:00:00"
#   }
```

**Signal conditions:**
- **BUY:** EMA8 > EMA21 > EMA50 · RSI in (35, 65) · price inside Bollinger Bands · volume > 50-period avg
- **SELL:** EMA8 < EMA21 < EMA50 · same filters
- **SL/TP:** Calculated dynamically from ATR at signal time

---

### `backtester.py` — Walk-forward backtester

Simulates the strategy candle-by-candle with spread costs and compounding.

```python
from backtester import BacktestConfig, run_backtest
from strategy import StrategyConfig

result = run_backtest(df, BacktestConfig(
    epic="GOLD",
    timeframe="DAY",
    initial_capital=300.0,
    risk_pct=1.5,
    spread_points=0.5,      # typical Capital.com Gold spread
    strategy=StrategyConfig(),
))

# Access results
print(result.stats)         # full metrics dict
print(result.trades)        # list of individual trades
print(result.equity_curve)  # [{time, equity}, ...] for charting
```

**Metrics returned:** `win_rate_pct` · `profit_factor` · `total_return_pct` · `max_drawdown_pct` · `avg_win_money` · `avg_loss_money` · `expectancy_per_trade` · `max_win_streak` · `max_loss_streak` · `total_spread_cost`

---

### `trader.py` — Live trading loop

Runs in a background thread. Checks signals every `check_interval` seconds and manages positions.

```python
from trader import LiveTrader
from strategy import StrategyConfig

trader = LiveTrader(
    epic="GOLD",
    timeframe="DAY",
    risk_pct=1.5,
    max_positions=2,
    check_interval=3600,     # check every hour
    strategy_cfg=StrategyConfig(),
)

trader.start()
# ... runs in background thread
trader.stop()
```

---

## REST API Reference

Base URL: `http://localhost:8000`

| Method | Endpoint | Description | Body |
|--------|----------|-------------|------|
| `GET` | `/api/status` | Bot status, open positions, balance | — |
| `GET` | `/api/balance` | Account balance | — |
| `GET` | `/api/positions` | All open positions | — |
| `GET` | `/api/trade-log` | History of bot-opened trades | — |
| `GET` | `/api/market/{epic}` | Price + current signal | `?timeframe=DAY` |
| `GET` | `/api/presets` | List available strategy presets | — |
| `POST` | `/api/backtest` | Run a backtest | [BacktestRequest](#mode-2--backtesting) |
| `POST` | `/api/start` | Start live bot | [StartRequest](#mode-3--live-trading) |
| `POST` | `/api/stop` | Stop live bot | — |
| `WS` | `/ws` | Real-time events stream | — |

**WebSocket events:**
```
price_update   → { epic, price, equity, timestamp }
trade_opened   → { deal_id, direction, entry_price, stop_loss, take_profit }
stopped        → {}
error          → { message }
```

---

## Capital.com API

Aurex is built on the [Capital.com REST API](https://open-api.capital.com/).

### Free demo account — no deposit required

1. Create a free account at [capital.com](https://capital.com)
2. Enable 2FA in account settings
3. Go to **Settings → API Management** → generate an API key
4. Set `CAPITAL_MODE=DEMO` in `.env`

You get **$100,000 in virtual funds** and **full API access** — same endpoints as live trading. This is enough to:
- Pull historical OHLCV data for any instrument
- Stream real-time prices via WebSocket
- Test and backtest strategies
- Run Aurex in full simulation mode

No credit card, no deposit, no commitment.

### Key endpoints used by Aurex

| Endpoint | Description |
|----------|-------------|
| `POST /session` | Authenticate and get session tokens |
| `GET /accounts` | Account balance and details |
| `GET /prices/{epic}` | Historical OHLCV (up to 1000 candles) |
| `GET /markets` | Search available instruments |
| `GET /markets/{epic}` | Instrument details and current price |
| `GET /positions` | Open positions |
| `POST /positions` | Open a new position |
| `PUT /positions/{dealId}` | Update SL/TP on open position |
| `DELETE /positions/{dealId}` | Close a position |

**Base URLs:**
```
Demo:  https://demo-api-capital.backend-capital.com/api/v1
Live:  https://api-capital.backend-capital.com/api/v1
```

**Rate limits:** 10 requests/sec · Session expires after 10 min of inactivity (auto-renewed)

**Official resources:**
- API Docs: https://open-api.capital.com/
- Postman collection: https://github.com/capital-com-sv/capital-api-postman

---

## Architecture

```
aurex/
├── bot-centralizado/
│   ├── backend/
│   │   ├── main.py            # FastAPI app — REST + WebSocket
│   │   ├── capital_client.py  # Capital.com API wrapper
│   │   ├── strategy.py        # Signal logic (EMA/RSI/ATR/BB)
│   │   ├── backtester.py      # Walk-forward backtester
│   │   ├── trader.py          # Live trading loop
│   │   └── requirements.txt
│   └── frontend/
│       ├── src/
│       │   ├── views/
│       │   │   ├── Dashboard.vue   # Live P&L and positions
│       │   │   ├── Backtest.vue    # Run backtests + equity chart
│       │   │   └── Settings.vue    # Bot configuration
│       │   └── stores/trading.js   # Pinia state management
│       ├── package.json
│       └── vite.config.js
├── docs/
│   └── xauusd_original_strategy.pine  # Original TradingView Pine Script
├── .env.example
└── README.md
```

> **Note:** `bot-centralizado/` will be flattened to `backend/` + `frontend/` at root in the next release.

---

## For AI Agents

```yaml
project: aurex
type: algorithmic-trading-system
language: python + javascript
framework: fastapi + vue3
broker: capital.com
instruments: any Capital.com epic (GOLD, US500, US100, NVDA, AAPL, EURUSD, BTCUSD, etc.)
strategy: triple-ema-crossover + rsi + bollinger-bands + atr
strategy_presets: [SWING, SCALP, SWING_CONSERVATIVE]

modules:
  capital_client:
    file: bot-centralizado/backend/capital_client.py
    purpose: Capital.com REST API wrapper
    key_methods: [login, get_prices, get_balance, get_positions, open_position, close_position]
    auth: api_key + email + password via POST /session
    session_expiry: 10min (auto-renewed via ensure_session)

  strategy:
    file: bot-centralizado/backend/strategy.py
    purpose: indicator calculation and signal generation
    inputs: OHLCV dataframe
    outputs: buy_signal, sell_signal, sl_distance, tp_distance per candle
    entry_conditions:
      long: ema_fast > ema_slow > ema_long AND rsi in (35,65) AND price inside BB AND volume > sma50
      short: ema_fast < ema_slow < ema_long AND same filters

  backtester:
    file: bot-centralizado/backend/backtester.py
    purpose: walk-forward simulation with spread costs and compounding
    inputs: OHLCV dataframe + BacktestConfig
    outputs: BacktestResult (trades, equity_curve, stats)

  trader:
    file: bot-centralizado/backend/trader.py
    purpose: live trading loop in background thread
    behaviour: checks signals every check_interval seconds, opens/closes positions

  api:
    file: bot-centralizado/backend/main.py
    framework: fastapi
    port: 8000
    endpoints: [/api/status, /api/balance, /api/positions, /api/backtest, /api/start, /api/stop, /api/market/{epic}, /api/presets, /ws]

config:
  env_file: bot-centralizado/backend/.env
  required_vars: [CAPITAL_API_KEY, CAPITAL_PASSWORD, CAPITAL_EMAIL, CAPITAL_MODE]
  modes: [DEMO, REAL]

dependencies:
  python: [fastapi, uvicorn, pandas, numpy, requests, python-dotenv]
  node: [vue3, vite, pinia, chart.js]

capital_api:
  docs: https://open-api.capital.com/
  demo_url: https://demo-api-capital.backend-capital.com/api/v1
  live_url: https://api-capital.backend-capital.com/api/v1
  free_demo: true
  deposit_required: false
```

---

## Risk Warning

This software is provided for educational and research purposes. Algorithmic trading involves significant financial risk. Past backtest performance does not guarantee future results. Always start in DEMO mode and never risk capital you cannot afford to lose.

---

## License

MIT
