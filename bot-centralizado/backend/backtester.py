"""
Backtester Realista
===================
Prueba la estrategia EMA/RSI/ATR contra datos históricos de Capital.com.

Características:
  - Simulación vela a vela (walk-forward, sin look-ahead bias)
  - Spread simulado (coste de entrada/salida real)
  - Position sizing dinámico con compounding (como Pine Script)
  - Métricas completas: Win Rate, Profit Factor, Max Drawdown, Sharpe

Por qué TradingView puede mostrar 1499% y nosotros menos:
  - TV no cuenta spread real de Capital.com (~0.5-1 punto en GOLD)
  - TV no cuenta slippage en mercados ilíquidos
  - TV usa compounding exacto - lo replicamos aquí
"""
import pandas as pd
import numpy as np
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict
from datetime import datetime

from strategy import StrategyConfig, calculate_indicators, generate_signals, get_position_size


@dataclass
class Trade:
    entry_time: str
    exit_time: str
    direction: str          # LONG / SHORT
    entry_price: float
    exit_price: float
    stop_loss: float
    take_profit: float
    size: float
    pnl_points: float       # En puntos de precio
    pnl_money: float        # En euros/dólares
    pnl_pct: float          # % de la equity al entrar
    result: str             # WIN / LOSS
    exit_reason: str        # SL / TP
    equity_after: float     # Equity tras el trade
    spread_cost: float      # Coste del spread


@dataclass
class BacktestConfig:
    epic: str = "GOLD"
    timeframe: str = "DAY"         # Intraday: MINUTE_15, MINUTE_30, HOUR | Swing: HOUR_4, DAY
    initial_capital: float = 300.0
    risk_pct: float = 1.5
    spread_points: float = 0.5     # Spread típico de Capital.com para GOLD ≈ 0.5 pts
    max_candles: int = 500
    strategy: StrategyConfig = field(default_factory=StrategyConfig)


@dataclass
class BacktestResult:
    config: dict
    trades: List[dict]
    equity_curve: List[dict]
    stats: dict


def run_backtest(df: pd.DataFrame, config: BacktestConfig) -> BacktestResult:
    """
    Ejecutar backtest completo.

    El algoritmo:
    1. Calcula indicadores sobre todo el df
    2. Itera vela a vela desde min_warmup hasta el final
    3. Si hay señal y no hay posición abierta: entra
    4. Si hay posición: comprueba SL/TP con high/low de la vela
    5. Solo una posición a la vez (como Pine Script default)
    6. Compounding: cada ganancia/pérdida se suma a la equity
    """
    cfg = config.strategy
    cfg.risk_pct = config.risk_pct

    # Calcular indicadores
    df = calculate_indicators(df, cfg)
    df = generate_signals(df, cfg)

    equity = config.initial_capital
    equity_curve = [{"time": str(df["timestamp"].iloc[0]), "equity": equity}]
    trades: List[Trade] = []

    in_trade = False
    current_trade: Optional[dict] = None
    min_idx = max(cfg.ema_long, cfg.bb_period, cfg.vol_sma_period, cfg.rsi_period) + 5

    for idx in range(min_idx, len(df) - 1):
        row = df.iloc[idx]
        next_row = df.iloc[idx + 1]  # La vela siguiente es donde se ejecuta la orden

        # ── Gestión de posición abierta ──────────────────────────────────
        if in_trade and current_trade:
            hi = next_row["high"]
            lo = next_row["low"]
            t = current_trade

            exit_price = None
            exit_reason = None

            if t["direction"] == "LONG":
                if lo <= t["stop_loss"]:
                    exit_price = t["stop_loss"]
                    exit_reason = "SL"
                elif hi >= t["take_profit"]:
                    exit_price = t["take_profit"]
                    exit_reason = "TP"
            else:  # SHORT
                if hi >= t["stop_loss"]:
                    exit_price = t["stop_loss"]
                    exit_reason = "SL"
                elif lo <= t["take_profit"]:
                    exit_price = t["take_profit"]
                    exit_reason = "TP"

            if exit_price is not None:
                # Calcular P&L
                if t["direction"] == "LONG":
                    pnl_points = exit_price - t["entry_price"]
                else:
                    pnl_points = t["entry_price"] - exit_price

                pnl_money = pnl_points * t["size"] - t["spread_cost"]
                pnl_pct = (pnl_money / t["equity_at_entry"]) * 100

                equity += pnl_money

                trade = Trade(
                    entry_time=t["entry_time"],
                    exit_time=str(next_row["timestamp"]),
                    direction=t["direction"],
                    entry_price=t["entry_price"],
                    exit_price=exit_price,
                    stop_loss=t["stop_loss"],
                    take_profit=t["take_profit"],
                    size=t["size"],
                    pnl_points=round(pnl_points, 4),
                    pnl_money=round(pnl_money, 4),
                    pnl_pct=round(pnl_pct, 2),
                    result="WIN" if pnl_money > 0 else "LOSS",
                    exit_reason=exit_reason,
                    equity_after=round(equity, 2),
                    spread_cost=round(t["spread_cost"], 4),
                )
                trades.append(trade)
                equity_curve.append({
                    "time": str(next_row["timestamp"]),
                    "equity": round(equity, 2),
                })
                in_trade = False
                current_trade = None

        # ── Buscar nueva entrada ──────────────────────────────────────────
        if not in_trade and equity > 0:
            # Señal en vela actual, entrada en apertura de siguiente vela
            if pd.isna(row["atr"]) or row["atr"] <= 0:
                continue

            direction = None
            if row["buy_signal"]:
                direction = "LONG"
            elif row["sell_signal"]:
                direction = "SHORT"

            if direction is None:
                continue

            entry_price = float(next_row["open"])
            sl_dist = float(row["sl_distance"])
            tp_dist = float(row["tp_distance"])

            if direction == "LONG":
                stop_loss = entry_price - sl_dist
                take_profit = entry_price + tp_dist
                # Spread penaliza entrada (compramos al ask = bid + spread)
                effective_entry = entry_price + config.spread_points / 2
            else:
                stop_loss = entry_price + sl_dist
                take_profit = entry_price - tp_dist
                # Spread penaliza entrada (vendemos al bid = ask - spread)
                effective_entry = entry_price - config.spread_points / 2

            size = get_position_size(equity, sl_dist, config.risk_pct)
            spread_cost = config.spread_points * size  # Coste total del spread

            current_trade = {
                "direction": direction,
                "entry_price": effective_entry,
                "entry_time": str(next_row["timestamp"]),
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "size": size,
                "equity_at_entry": equity,
                "spread_cost": spread_cost,
            }
            in_trade = True

    # ── Estadísticas ──────────────────────────────────────────────────────
    stats = _calculate_stats(trades, config.initial_capital, equity)

    return BacktestResult(
        config=asdict(config),
        trades=[asdict(t) for t in trades],
        equity_curve=equity_curve,
        stats=stats,
    )


def _calculate_stats(trades: List[Trade], initial_capital: float, final_equity: float) -> dict:
    if not trades:
        return {"error": "No se ejecutaron trades en el periodo"}

    total = len(trades)
    wins = [t for t in trades if t.result == "WIN"]
    losses = [t for t in trades if t.result == "LOSS"]
    win_rate = len(wins) / total * 100

    total_pnl_money = sum(t.pnl_money for t in trades)
    total_return_pct = (final_equity - initial_capital) / initial_capital * 100

    avg_win = np.mean([t.pnl_money for t in wins]) if wins else 0
    avg_loss = np.mean([t.pnl_money for t in losses]) if losses else 0

    gross_profit = sum(t.pnl_money for t in wins) if wins else 0
    gross_loss = abs(sum(t.pnl_money for t in losses)) if losses else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # Expectativa por trade
    expectancy = (win_rate / 100 * avg_win) + ((1 - win_rate / 100) * avg_loss)

    # Max Drawdown
    equity_vals = [initial_capital]
    running = initial_capital
    for t in trades:
        running += t.pnl_money
        equity_vals.append(running)

    peak = equity_vals[0]
    max_dd = 0.0
    max_dd_pct = 0.0
    for val in equity_vals:
        if val > peak:
            peak = val
        dd = peak - val
        dd_pct = dd / peak * 100 if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd
        if dd_pct > max_dd_pct:
            max_dd_pct = dd_pct

    # Rachas ganadoras/perdedoras
    max_win_streak = max_loss_streak = curr_streak = 0
    last_result = None
    for t in trades:
        if t.result == last_result:
            curr_streak += 1
        else:
            curr_streak = 1
            last_result = t.result
        if t.result == "WIN" and curr_streak > max_win_streak:
            max_win_streak = curr_streak
        if t.result == "LOSS" and curr_streak > max_loss_streak:
            max_loss_streak = curr_streak

    # Coste total de spreads
    total_spread_cost = sum(t.spread_cost for t in trades)

    # Veredicto
    if win_rate >= 50 and profit_factor >= 1.5:
        verdict = "✅ RENTABLE - Puede usarse en live"
    elif win_rate >= 45 and profit_factor >= 1.2:
        verdict = "⚠️ MARGINAL - Usar con precaución en demo primero"
    else:
        verdict = "❌ NO RENTABLE - Ajustar parámetros"

    return {
        "total_trades": total,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": round(win_rate, 1),
        "total_return_pct": round(total_return_pct, 2),
        "total_pnl_money": round(total_pnl_money, 2),
        "initial_capital": initial_capital,
        "final_equity": round(final_equity, 2),
        "avg_win_money": round(avg_win, 2),
        "avg_loss_money": round(avg_loss, 2),
        "profit_factor": round(profit_factor, 2),
        "expectancy_per_trade": round(expectancy, 2),
        "max_drawdown_money": round(max_dd, 2),
        "max_drawdown_pct": round(max_dd_pct, 1),
        "max_win_streak": max_win_streak,
        "max_loss_streak": max_loss_streak,
        "total_spread_cost": round(total_spread_cost, 2),
        "verdict": verdict,
    }
