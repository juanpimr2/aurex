"""
Aurex — API Backend (FastAPI)
==============================
REST + WebSocket API for the Aurex algorithmic trading system.

Interactive docs:
  Swagger UI  → http://localhost:8000/docs
  ReDoc       → http://localhost:8000/redoc
  OpenAPI JSON→ http://localhost:8000/openapi.json
"""
import asyncio
import json
from typing import Any, Dict, List, Optional
from datetime import datetime

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from capital_client import CapitalClient
from strategy import StrategyConfig, STRATEGY_PRESETS
from backtester import BacktestConfig, run_backtest
from trader import LiveTrader


# ── App metadata ───────────────────────────────────────────────────────────

app = FastAPI(
    title="Aurex Trading API",
    version="2.1.0",
    description="""
Algorithmic trading system for Capital.com.

Supports **Gold, Stocks (NVDA, AAPL, TSLA), Indices (US500, US100), Forex, and Crypto**
via a triple EMA crossover strategy enhanced with RSI, Bollinger Bands, and ATR-based
risk management.

## Features
- **Market analysis** — real-time signals for any Capital.com instrument
- **Backtesting** — walk-forward simulation with spread costs and compounding
- **Live trading** — automated position management with configurable risk
- **Strategy presets** — SWING / SCALP / SWING_CONSERVATIVE ready to use

## Instruments
Use the Capital.com epic code: `GOLD`, `US500`, `US100`, `NVDA`, `AAPL`, `EURUSD`, `BTCUSD`, etc.

## Quick start
```bash
# Market signal
curl http://localhost:8000/api/market/GOLD?timeframe=DAY

# Backtest 500 EUR on NVIDIA with SWING preset
curl -X POST http://localhost:8000/api/backtest \\
  -H "Content-Type: application/json" \\
  -d '{"epic": "NVDA", "initial_capital": 500, "preset": "SWING"}'

# Start live bot
curl -X POST http://localhost:8000/api/start \\
  -H "Content-Type: application/json" \\
  -d '{"epic": "GOLD", "preset": "SWING", "risk_pct": 1.5}'
```
""",
    contact={
        "name": "Aurex",
        "url": "https://github.com/juanpimr2/aurex",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
    openapi_tags=[
        {
            "name": "market",
            "description": "Real-time price data and strategy signals for any Capital.com instrument.",
        },
        {
            "name": "backtest",
            "description": "Walk-forward backtesting against real historical data. Supports strategy presets and custom parameters.",
        },
        {
            "name": "live",
            "description": "Start, stop, and monitor the live trading bot.",
        },
        {
            "name": "account",
            "description": "Capital.com account balance and open positions.",
        },
        {
            "name": "strategy",
            "description": "Strategy preset definitions — SWING, SCALP, SWING_CONSERVATIVE.",
        },
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global state ───────────────────────────────────────────────────────────
_trader: Optional[LiveTrader] = None
_ws_clients: List[WebSocket] = []


def _broadcast(event: dict):
    """Send event to all connected WebSocket clients."""
    dead = []
    for ws in _ws_clients:
        try:
            asyncio.create_task(ws.send_text(json.dumps(event, default=str)))
        except Exception:
            dead.append(ws)
    for d in dead:
        _ws_clients.remove(d)


# ── Request / Response models ──────────────────────────────────────────────

class BacktestRequest(BaseModel):
    epic: str = Field(
        default="GOLD",
        description="Capital.com instrument epic code.",
        examples=["GOLD", "NVDA", "US500", "BTCUSD", "EURUSD"],
    )
    timeframe: str = Field(
        default="DAY",
        description="Candle resolution. Recommended: DAY for SWING, HOUR for SCALP.",
        examples=["MINUTE", "MINUTE_5", "MINUTE_15", "MINUTE_30", "HOUR", "HOUR_4", "DAY", "WEEK"],
    )
    initial_capital: float = Field(
        default=300.0,
        gt=0,
        description="Starting capital in account currency (EUR, USD, etc.).",
        examples=[300.0, 500.0, 1000.0],
    )
    risk_pct: float = Field(
        default=1.5,
        gt=0,
        le=10,
        description="Percentage of equity risked per trade. Recommended: 1–2%.",
        examples=[1.0, 1.5, 2.0],
    )
    spread_points: float = Field(
        default=0.5,
        ge=0,
        description="Simulated spread in price points. Typical Capital.com Gold spread ≈ 0.5.",
    )
    max_candles: int = Field(
        default=500,
        ge=100,
        le=1000,
        description="Number of historical candles to fetch (max 1000).",
    )
    preset: Optional[str] = Field(
        default=None,
        description="Strategy preset name. If set, overrides individual EMA/RSI/ATR params.",
        examples=["SWING", "SCALP", "SWING_CONSERVATIVE"],
    )
    # Manual strategy params (ignored if preset is set)
    ema_fast: int = Field(default=8, description="Fast EMA period.")
    ema_slow: int = Field(default=21, description="Slow EMA period.")
    ema_long: int = Field(default=50, description="Long EMA period.")
    rsi_period: int = Field(default=14, description="RSI calculation period.")
    rsi_overbought: float = Field(default=65.0, description="RSI overbought threshold (no entry above).")
    rsi_oversold: float = Field(default=35.0, description="RSI oversold threshold (no entry below).")
    atr_period: int = Field(default=14, description="ATR calculation period.")
    atr_sl_mult: float = Field(
        default=2.0,
        description="Stop loss = ATR × multiplier. Professional standard: 2.0–2.5×.",
        examples=[1.5, 2.0, 2.5],
    )
    atr_tp_mult: float = Field(
        default=2.5,
        description="Take profit = ATR × multiplier. R:R ratio = atr_sl_mult : atr_tp_mult.",
        examples=[2.0, 2.5, 3.0],
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "summary": "500 EUR on NVIDIA — SWING preset",
                    "value": {
                        "epic": "NVDA",
                        "timeframe": "DAY",
                        "initial_capital": 500,
                        "preset": "SWING",
                    },
                },
                {
                    "summary": "500 EUR on S&P 500 — SCALP preset",
                    "value": {
                        "epic": "US500",
                        "timeframe": "HOUR",
                        "initial_capital": 500,
                        "preset": "SCALP",
                    },
                },
                {
                    "summary": "Gold — manual parameters",
                    "value": {
                        "epic": "GOLD",
                        "timeframe": "DAY",
                        "initial_capital": 300,
                        "risk_pct": 1.5,
                        "spread_points": 0.5,
                        "max_candles": 500,
                        "ema_fast": 8,
                        "ema_slow": 21,
                        "ema_long": 50,
                        "atr_sl_mult": 2.0,
                        "atr_tp_mult": 2.5,
                    },
                },
            ]
        }
    }


class StartRequest(BaseModel):
    epic: str = Field(
        default="GOLD",
        description="Capital.com instrument epic code.",
        examples=["GOLD", "NVDA", "US500", "EURUSD"],
    )
    timeframe: str = Field(
        default="DAY",
        description="Candle resolution. Automatically set from preset if provided.",
    )
    risk_pct: float = Field(
        default=1.5,
        gt=0,
        le=10,
        description="Percentage of equity risked per trade.",
    )
    max_positions: int = Field(
        default=2,
        ge=1,
        le=10,
        description="Maximum number of simultaneous open positions.",
    )
    check_interval: int = Field(
        default=3600,
        ge=60,
        description="Seconds between signal checks. Automatically set from preset if provided.",
        examples=[1800, 3600, 7200],
    )
    preset: Optional[str] = Field(
        default=None,
        description="Strategy preset. Sets timeframe, EMA, ATR params, and check_interval automatically.",
        examples=["SWING", "SCALP", "SWING_CONSERVATIVE"],
    )
    # Manual params (ignored if preset is set)
    ema_fast: int = Field(default=8, description="Fast EMA period.")
    ema_slow: int = Field(default=21, description="Slow EMA period.")
    ema_long: int = Field(default=50, description="Long EMA period.")
    rsi_period: int = Field(default=14, description="RSI period.")
    atr_sl_mult: float = Field(default=2.0, description="Stop loss ATR multiplier.")
    atr_tp_mult: float = Field(default=2.5, description="Take profit ATR multiplier.")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "summary": "Gold swing trading",
                    "value": {"epic": "GOLD", "preset": "SWING", "risk_pct": 1.5, "max_positions": 2},
                },
                {
                    "summary": "NVIDIA scalping",
                    "value": {"epic": "NVDA", "preset": "SCALP", "risk_pct": 1.0, "max_positions": 1},
                },
            ]
        }
    }


# ── Endpoints ──────────────────────────────────────────────────────────────

@app.get(
    "/api/presets",
    tags=["strategy"],
    summary="List strategy presets",
    response_description="Available strategy presets with description and recommended parameters.",
)
def get_presets() -> Dict[str, Any]:
    """
    Returns all available strategy presets.

    Each preset defines a complete trading configuration:
    - **SWING** — daily timeframe, wide SL (2× ATR). Best for Gold, indices.
    - **SCALP** — hourly timeframe, tighter SL (1.5× ATR). Best for forex, crypto.
    - **SWING_CONSERVATIVE** — daily timeframe, wider SL (2.5× ATR), 1% risk. For new accounts.

    Use the preset name in `/api/backtest` or `/api/start` via the `preset` field.
    """
    return {
        name: {
            "name": p["name"],
            "description": p["description"],
            "recommended_timeframe": p["recommended_timeframe"],
            "check_interval_sec": p["check_interval_sec"],
        }
        for name, p in STRATEGY_PRESETS.items()
    }


@app.get(
    "/api/status",
    tags=["live"],
    summary="Bot status",
    response_description="Current bot state, active configuration, and runtime stats.",
)
def get_status() -> Dict[str, Any]:
    """
    Returns whether the live trading bot is running, and if so, its current configuration
    and runtime statistics (trades executed, last signal, equity).
    """
    global _trader
    if _trader is None:
        return {"running": False, "trader": None}
    return {"running": True, "trader": _trader.get_status()}


@app.get(
    "/api/balance",
    tags=["account"],
    summary="Account balance",
    response_description="Current Capital.com account balance and P&L.",
)
def get_balance() -> Dict[str, Any]:
    """
    Fetches the current balance from Capital.com.

    Returns the preferred account's `balance`, `available` funds, and open `profit_loss`.
    Requires valid credentials in `.env`.
    """
    client = CapitalClient()
    if not client.login():
        return {"error": "Could not connect to Capital.com"}
    bal = client.get_balance()
    return bal or {"error": "Could not retrieve balance"}


@app.get(
    "/api/positions",
    tags=["account"],
    summary="Open positions",
    response_description="List of currently open positions on Capital.com.",
)
def get_positions() -> List[Dict[str, Any]]:
    """
    Returns all currently open positions on the Capital.com account.

    Each position includes: `deal_id`, `epic`, `direction` (BUY/SELL), `size`,
    `entry_price`, `stop_loss`, `take_profit`, `profit_loss`, `created_at`.
    """
    client = CapitalClient()
    if not client.login():
        return []
    return client.get_positions()


@app.get(
    "/api/trade-log",
    tags=["live"],
    summary="Trade history",
    response_description="List of trades opened by the bot in the current session.",
)
def get_trade_log() -> List[Dict[str, Any]]:
    """
    Returns the trade history for the current bot session.

    Note: this is in-memory only. History resets when the server restarts.
    """
    global _trader
    if _trader is None:
        return []
    return _trader.trade_log


@app.get(
    "/api/market/{epic}",
    tags=["market"],
    summary="Market signal",
    response_description="Current price, strategy signal, and indicator values for the requested instrument.",
)
def get_market(
    epic: str,
    timeframe: str = Query(
        default="HOUR",
        description="Candle resolution.",
        examples=["MINUTE", "HOUR", "HOUR_4", "DAY"],
    ),
) -> Dict[str, Any]:
    """
    Returns the current price and strategy signal for any Capital.com instrument.

    **Epic codes (examples):**

    | Instrument | Epic |
    |---|---|
    | Gold | `GOLD` |
    | S&P 500 | `US500` |
    | Nasdaq 100 | `US100` |
    | NVIDIA | `NVDA` |
    | EUR/USD | `EURUSD` |
    | Bitcoin | `BTCUSD` |

    Signal is generated from the last **complete** candle (penultimate row) to avoid look-ahead bias.

    Signal conditions:
    - **BUY**: EMA8 > EMA21 > EMA50 · RSI in (35, 65) · price inside Bollinger Bands · volume above average
    - **SELL**: EMA8 < EMA21 < EMA50 · same filters
    - **NONE**: no clear trend or filters not met
    """
    from strategy import calculate_indicators, generate_signals, StrategyConfig
    client = CapitalClient()
    if not client.login():
        return {"error": "Could not connect to Capital.com"}

    df = client.get_prices(epic, timeframe, 200)
    if df is None:
        return {"error": f"No data available for {epic}"}

    cfg = StrategyConfig()
    df = calculate_indicators(df, cfg)
    df = generate_signals(df, cfg)
    last = df.iloc[-2]

    return {
        "epic": epic,
        "timeframe": timeframe,
        "current_price": float(df["close"].iloc[-1]),
        "signal": "BUY" if last["buy_signal"] else "SELL" if last["sell_signal"] else "NONE",
        "rsi": round(float(last["rsi"]), 1),
        "atr": round(float(last["atr"]), 4),
        "ema_fast": round(float(last["ema_fast"]), 4),
        "ema_slow": round(float(last["ema_slow"]), 4),
        "ema_long": round(float(last["ema_long"]), 4),
        "bb_upper": round(float(last["bb_upper"]), 4),
        "bb_lower": round(float(last["bb_lower"]), 4),
        "timestamp": str(df["timestamp"].iloc[-1]),
        "last_candles": df[["timestamp", "open", "high", "low", "close"]].tail(5).to_dict("records"),
    }


@app.post(
    "/api/backtest",
    tags=["backtest"],
    summary="Run backtest",
    response_description="Backtest statistics, equity curve, and individual trade list.",
)
async def run_backtest_endpoint(req: BacktestRequest) -> Dict[str, Any]:
    """
    Runs a walk-forward backtest against real Capital.com historical data.

    ## How it works
    1. Downloads up to `max_candles` OHLCV candles from Capital.com
    2. Simulates the strategy candle-by-candle (no look-ahead bias)
    3. Applies spread costs on every entry and exit
    4. Uses compounding — each P&L updates the equity for the next trade

    ## Using presets
    Send `"preset": "SWING"` (or `"SCALP"` / `"SWING_CONSERVATIVE"`) to use a
    pre-configured strategy. Individual EMA/RSI/ATR params are ignored when preset is set.

    ## Returned metrics
    `win_rate_pct`, `profit_factor`, `total_return_pct`, `max_drawdown_pct`,
    `avg_win_money`, `avg_loss_money`, `expectancy_per_trade`, `max_win_streak`,
    `max_loss_streak`, `total_spread_cost`, `verdict`
    """
    client = CapitalClient()
    if not client.login():
        return {"error": "Could not connect to Capital.com"}

    df = client.get_prices(req.epic, req.timeframe, req.max_candles)
    if df is None or len(df) < 100:
        return {"error": f"Not enough data for {req.epic}. Try a different instrument or timeframe."}

    if req.preset and req.preset in STRATEGY_PRESETS:
        preset_params = STRATEGY_PRESETS[req.preset]["params"]
        strategy_cfg = StrategyConfig(**preset_params)
        strategy_cfg.risk_pct = req.risk_pct
    else:
        strategy_cfg = StrategyConfig(
            ema_fast=req.ema_fast,
            ema_slow=req.ema_slow,
            ema_long=req.ema_long,
            rsi_period=req.rsi_period,
            rsi_overbought=req.rsi_overbought,
            rsi_oversold=req.rsi_oversold,
            atr_period=req.atr_period,
            atr_sl_mult=req.atr_sl_mult,
            atr_tp_mult=req.atr_tp_mult,
            risk_pct=req.risk_pct,
        )

    bt_config = BacktestConfig(
        epic=req.epic,
        timeframe=req.timeframe,
        initial_capital=req.initial_capital,
        risk_pct=req.risk_pct,
        spread_points=req.spread_points,
        max_candles=req.max_candles,
        strategy=strategy_cfg,
    )

    result = run_backtest(df, bt_config)

    return {
        "stats": result.stats,
        "equity_curve": result.equity_curve,
        "trades": result.trades[-100:],
        "total_candles": len(df),
        "date_range": {
            "start": str(df["timestamp"].iloc[0]),
            "end": str(df["timestamp"].iloc[-1]),
        },
    }


@app.post(
    "/api/start",
    tags=["live"],
    summary="Start live bot",
    response_description="Confirmation message with active epic, timeframe, and preset.",
)
def start_trading(req: StartRequest) -> Dict[str, Any]:
    """
    Starts the live trading bot in a background thread.

    The bot checks for signals every `check_interval` seconds. When a signal is detected
    and position limits allow it, it opens a position with ATR-based SL and TP.

    ## Using presets
    `"preset": "SWING"` automatically configures timeframe (`DAY`), EMA periods,
    ATR multipliers, and check interval (3600s). Manual params are ignored.

    ## Safety
    - Always test with `CAPITAL_MODE=DEMO` in `.env` before switching to REAL.
    - The bot will not open more positions than `max_positions`.
    - Risk per trade is capped to `risk_pct`% of current equity (compounding).
    """
    global _trader
    if _trader and _trader.status["running"]:
        return {"error": "Bot is already running"}

    if req.preset and req.preset in STRATEGY_PRESETS:
        preset = STRATEGY_PRESETS[req.preset]
        cfg = StrategyConfig(**preset["params"])
        cfg.risk_pct = req.risk_pct
        timeframe = req.timeframe if req.timeframe != "DAY" else preset["recommended_timeframe"]
        check_interval = preset["check_interval_sec"]
        preset_label = req.preset
    else:
        cfg = StrategyConfig(
            ema_fast=req.ema_fast,
            ema_slow=req.ema_slow,
            ema_long=req.ema_long,
            rsi_period=req.rsi_period,
            atr_sl_mult=req.atr_sl_mult,
            atr_tp_mult=req.atr_tp_mult,
        )
        cfg.risk_pct = req.risk_pct
        timeframe = req.timeframe
        check_interval = req.check_interval
        preset_label = "MANUAL"

    _trader = LiveTrader(
        epic=req.epic,
        timeframe=timeframe,
        risk_pct=req.risk_pct,
        max_positions=req.max_positions,
        check_interval=check_interval,
        strategy_cfg=cfg,
        on_event=_broadcast,
    )

    if _trader.start():
        return {"ok": True, "message": f"Bot started: {req.epic} @ {timeframe} ({preset_label})"}
    return {"error": "Could not start bot. Check credentials in .env"}


@app.post(
    "/api/stop",
    tags=["live"],
    summary="Stop live bot",
    response_description="Confirmation that the bot has been stopped.",
)
def stop_trading() -> Dict[str, Any]:
    """
    Stops the live trading bot gracefully.

    Open positions are **not** automatically closed — they remain on Capital.com
    and can be managed manually or via `/api/positions`.
    """
    global _trader
    if _trader is None or not _trader.status["running"]:
        return {"error": "Bot is not running"}
    _trader.stop()
    return {"ok": True, "message": "Bot stopped"}


# ── WebSocket ──────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Real-time event stream.

    Events:
    - `price_update` — `{ epic, price, equity, timestamp }`
    - `trade_opened` — `{ deal_id, direction, entry_price, stop_loss, take_profit }`
    - `trade_closed` — `{ deal_id, exit_price, pnl, reason }`
    - `stopped`      — `{}`
    - `ping`         — `{ ts }` (keepalive, every 30s)
    """
    await websocket.accept()
    _ws_clients.append(websocket)
    try:
        while True:
            await asyncio.sleep(30)
            await websocket.send_text(json.dumps({"type": "ping", "ts": datetime.now().isoformat()}))
    except WebSocketDisconnect:
        if websocket in _ws_clients:
            _ws_clients.remove(websocket)


# ── Entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
