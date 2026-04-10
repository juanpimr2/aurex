"""
Bot Millonario - API Backend (FastAPI)
======================================
Endpoints REST + WebSocket para el dashboard Vue.

Rutas:
  GET  /api/status           → Estado del bot
  GET  /api/balance          → Balance de la cuenta
  GET  /api/positions        → Posiciones abiertas
  GET  /api/trade-log        → Historial de trades del bot
  POST /api/backtest         → Ejecutar backtest
  POST /api/start            → Iniciar trading en vivo
  POST /api/stop             → Detener trading en vivo
  GET  /api/market/{epic}    → Info de mercado + señal actual
  WS   /ws                   → Updates en tiempo real
"""
import asyncio
import json
from typing import List, Optional
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from capital_client import CapitalClient
from strategy import StrategyConfig
from backtester import BacktestConfig, run_backtest
from trader import LiveTrader

app = FastAPI(title="Bot Millonario API", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Estado global ──────────────────────────────────────────────────────────
_trader: Optional[LiveTrader] = None
_ws_clients: List[WebSocket] = []


def _broadcast(event: dict):
    """Enviar evento a todos los clientes WebSocket conectados"""
    dead = []
    for ws in _ws_clients:
        try:
            asyncio.create_task(ws.send_text(json.dumps(event, default=str)))
        except Exception:
            dead.append(ws)
    for d in dead:
        _ws_clients.remove(d)


# ── Modelos Pydantic ───────────────────────────────────────────────────────

class BacktestRequest(BaseModel):
    epic: str = "GOLD"
    timeframe: str = "DAY"
    initial_capital: float = 300.0
    risk_pct: float = 1.5
    spread_points: float = 0.5
    max_candles: int = 500
    # Parámetros de estrategia (optimizados: DAY 500v, WR 46.7%, PF 2.26, +441%)
    ema_fast: int = 8
    ema_slow: int = 21
    ema_long: int = 50
    rsi_period: int = 14
    rsi_overbought: float = 65.0
    rsi_oversold: float = 35.0
    atr_period: int = 14
    atr_sl_mult: float = 1.0
    atr_tp_mult: float = 2.5


class StartRequest(BaseModel):
    epic: str = "GOLD"
    timeframe: str = "DAY"
    risk_pct: float = 1.5
    max_positions: int = 2
    check_interval: int = 3600      # DAY = revisar cada hora es suficiente
    ema_fast: int = 8
    ema_slow: int = 21
    ema_long: int = 50
    rsi_period: int = 14
    atr_sl_mult: float = 1.0
    atr_tp_mult: float = 2.5


# ── Endpoints REST ─────────────────────────────────────────────────────────

@app.get("/api/status")
def get_status():
    global _trader
    if _trader is None:
        return {"running": False, "trader": None}
    return {"running": True, "trader": _trader.get_status()}


@app.get("/api/balance")
def get_balance():
    client = CapitalClient()
    if not client.login():
        return {"error": "No se pudo conectar a Capital.com"}
    bal = client.get_balance()
    return bal or {"error": "No se pudo obtener balance"}


@app.get("/api/positions")
def get_positions():
    client = CapitalClient()
    if not client.login():
        return {"error": "No se pudo conectar"}
    return client.get_positions()


@app.get("/api/trade-log")
def get_trade_log():
    global _trader
    if _trader is None:
        return []
    return _trader.trade_log


@app.get("/api/market/{epic}")
def get_market(epic: str, timeframe: str = "HOUR"):
    """Precio actual + señal actual de la estrategia"""
    from strategy import calculate_indicators, generate_signals, StrategyConfig
    client = CapitalClient()
    if not client.login():
        return {"error": "No se pudo conectar"}

    df = client.get_prices(epic, timeframe, 200)
    if df is None:
        return {"error": "No hay datos para este activo"}

    cfg = StrategyConfig()
    df = calculate_indicators(df, cfg)
    df = generate_signals(df, cfg)
    last = df.iloc[-2]  # Última vela completa

    return {
        "epic": epic,
        "timeframe": timeframe,
        "current_price": float(df["close"].iloc[-1]),
        "signal": "BUY" if last["buy_signal"] else "SELL" if last["sell_signal"] else "NONE",
        "rsi": round(float(last["rsi"]), 1) if not float.__is_integer__ else None,
        "atr": round(float(last["atr"]), 4),
        "ema_fast": round(float(last["ema_fast"]), 4),
        "ema_slow": round(float(last["ema_slow"]), 4),
        "ema_long": round(float(last["ema_long"]), 4),
        "bb_upper": round(float(last["bb_upper"]), 4),
        "bb_lower": round(float(last["bb_lower"]), 4),
        "timestamp": str(df["timestamp"].iloc[-1]),
        "last_candles": df[["timestamp", "open", "high", "low", "close"]].tail(5).to_dict("records"),
    }


@app.post("/api/backtest")
async def run_backtest_endpoint(req: BacktestRequest):
    """
    Ejecutar backtest completo.
    Descarga datos de Capital.com y simula la estrategia.
    """
    client = CapitalClient()
    if not client.login():
        return {"error": "No se pudo conectar a Capital.com"}

    df = client.get_prices(req.epic, req.timeframe, req.max_candles)
    if df is None or len(df) < 100:
        return {"error": f"No hay suficientes datos para {req.epic}. Prueba otro activo o timeframe."}

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
        "trades": result.trades[-100:],  # Últimos 100 trades para el UI
        "total_candles": len(df),
        "date_range": {
            "start": str(df["timestamp"].iloc[0]),
            "end": str(df["timestamp"].iloc[-1]),
        },
    }


@app.post("/api/start")
def start_trading(req: StartRequest):
    global _trader
    if _trader and _trader.status["running"]:
        return {"error": "El bot ya está corriendo"}

    cfg = StrategyConfig(
        ema_fast=req.ema_fast,
        ema_slow=req.ema_slow,
        ema_long=req.ema_long,
        rsi_period=req.rsi_period,
        atr_sl_mult=req.atr_sl_mult,
        atr_tp_mult=req.atr_tp_mult,
    )

    _trader = LiveTrader(
        epic=req.epic,
        timeframe=req.timeframe,
        risk_pct=req.risk_pct,
        max_positions=req.max_positions,
        check_interval=req.check_interval,
        strategy_cfg=cfg,
        on_event=_broadcast,
    )

    if _trader.start():
        return {"ok": True, "message": f"Bot iniciado: {req.epic} @ {req.timeframe}"}
    return {"error": "No se pudo iniciar el bot. Verifica las credenciales en .env"}


@app.post("/api/stop")
def stop_trading():
    global _trader
    if _trader is None or not _trader.status["running"]:
        return {"error": "El bot no está corriendo"}
    _trader.stop()
    return {"ok": True, "message": "Bot detenido"}


# ── WebSocket ──────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    _ws_clients.append(websocket)
    try:
        while True:
            # Mantener conexión viva
            await asyncio.sleep(30)
            await websocket.send_text(json.dumps({"type": "ping", "ts": datetime.now().isoformat()}))
    except WebSocketDisconnect:
        if websocket in _ws_clients:
            _ws_clients.remove(websocket)


# ── Entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
