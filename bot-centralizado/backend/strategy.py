"""
Estrategia EMA + RSI + Bollinger + ATR
=======================================
Implementación EXACTA de la estrategia del Pine Script:
  "XAUUSD Strategy - Control de Drawdown"

Parámetros por defecto:
  EMA rápida:   6
  EMA lenta:    18
  EMA larga:    30
  RSI:          14  (entrar si RSI entre 30-70, no en extremos)
  ATR SL mult:  0.8
  ATR TP mult:  2.0
  BB period:    20, desv: 2.0
  Vol mult:     1.0 (volumen > media de 50)
  Risk:         1.5% por operación
"""
import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Optional


@dataclass
class StrategyConfig:
    # Optimizado con backtest DAY 500 velas (Aug 2024 - Mar 2026):
    # EMA 8/21/50 | SL 1.0x | TP 2.5x | RSI 65/35
    # Win Rate: 46.7% | PF: 2.26 | Return: +441% | MaxDD: 26.9%
    ema_fast: int = 8
    ema_slow: int = 21
    ema_long: int = 50
    rsi_period: int = 14
    rsi_overbought: float = 65.0
    rsi_oversold: float = 35.0
    atr_period: int = 14
    atr_sl_mult: float = 1.0
    atr_tp_mult: float = 2.5
    bb_period: int = 20
    bb_std: float = 2.0
    vol_sma_period: int = 50
    vol_mult: float = 1.0
    risk_pct: float = 1.5   # % del capital por operación


def _calculate_rsi(series: pd.Series, period: int) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(window=period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _calculate_atr(df: pd.DataFrame, period: int) -> pd.Series:
    high, low, prev_close = df["high"], df["low"], df["close"].shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.rolling(window=period).mean()


def calculate_indicators(df: pd.DataFrame, cfg: StrategyConfig) -> pd.DataFrame:
    """
    Añade columnas de indicadores al DataFrame.
    El df de entrada debe tener: timestamp, open, high, low, close, volume
    """
    df = df.copy()

    # EMAs
    df["ema_fast"] = df["close"].ewm(span=cfg.ema_fast, adjust=False).mean()
    df["ema_slow"] = df["close"].ewm(span=cfg.ema_slow, adjust=False).mean()
    df["ema_long"] = df["close"].ewm(span=cfg.ema_long, adjust=False).mean()

    # RSI
    df["rsi"] = _calculate_rsi(df["close"], cfg.rsi_period)

    # ATR
    df["atr"] = _calculate_atr(df, cfg.atr_period)

    # Bollinger Bands
    df["bb_mid"] = df["close"].rolling(cfg.bb_period).mean()
    df["bb_std"] = df["close"].rolling(cfg.bb_period).std()
    df["bb_upper"] = df["bb_mid"] + cfg.bb_std * df["bb_std"]
    df["bb_lower"] = df["bb_mid"] - cfg.bb_std * df["bb_std"]

    # Volume SMA
    df["vol_sma"] = df["volume"].rolling(cfg.vol_sma_period).mean()

    return df


def generate_signals(df: pd.DataFrame, cfg: StrategyConfig) -> pd.DataFrame:
    """
    Genera señales BUY/SELL según la estrategia Pine Script.
    Devuelve df con columnas: buy_signal, sell_signal, sl_distance, tp_distance
    """
    df = df.copy()

    long_trend = (df["ema_fast"] > df["ema_slow"]) & (df["ema_slow"] > df["ema_long"])
    short_trend = (df["ema_fast"] < df["ema_slow"]) & (df["ema_slow"] < df["ema_long"])

    rsi_ok = (df["rsi"] > cfg.rsi_oversold) & (df["rsi"] < cfg.rsi_overbought)

    # Precio dentro de las bandas de Bollinger
    bb_ok = (df["close"] > df["bb_lower"]) & (df["close"] < df["bb_upper"])

    # Volumen por encima de la media (si vol_sma es 0/nan, ignorar condición)
    vol_ok = df["volume"] > (df["vol_sma"] * cfg.vol_mult)
    vol_ok = vol_ok | df["vol_sma"].isna() | (df["vol_sma"] == 0)

    df["buy_signal"] = long_trend & rsi_ok & bb_ok & vol_ok
    df["sell_signal"] = short_trend & rsi_ok & bb_ok & vol_ok

    # Distancias SL/TP en puntos de precio
    df["sl_distance"] = df["atr"] * cfg.atr_sl_mult
    df["tp_distance"] = df["atr"] * cfg.atr_tp_mult

    return df


def get_position_size(
    equity: float,
    sl_distance: float,
    risk_pct: float,
    min_size: float = 1.0,
) -> float:
    """
    Calcula el tamaño de posición basado en riesgo.
    position_size = equity * risk_pct% / sl_distance

    Sin cap artificial - si la estrategia pide un SL grande,
    el tamaño de posición será menor (gestión de riesgo correcta).
    """
    if sl_distance <= 0:
        return min_size
    risk_amount = equity * (risk_pct / 100.0)
    size = risk_amount / sl_distance
    return max(size, min_size)


def get_latest_signal(df: pd.DataFrame, cfg: StrategyConfig) -> Optional[dict]:
    """
    Devuelve la señal más reciente o None si no hay señal.
    """
    df = calculate_indicators(df, cfg)
    df = generate_signals(df, cfg)

    # Usar la última vela completa (penúltima fila para evitar look-ahead)
    last = df.iloc[-2]

    if pd.isna(last["atr"]) or pd.isna(last["rsi"]):
        return None

    if last["buy_signal"]:
        return {
            "direction": "BUY",
            "entry_price": float(last["close"]),
            "sl_distance": float(last["sl_distance"]),
            "tp_distance": float(last["tp_distance"]),
            "stop_loss": float(last["close"] - last["sl_distance"]),
            "take_profit": float(last["close"] + last["tp_distance"]),
            "rsi": float(last["rsi"]),
            "atr": float(last["atr"]),
            "timestamp": str(last["timestamp"]),
        }
    elif last["sell_signal"]:
        return {
            "direction": "SELL",
            "entry_price": float(last["close"]),
            "sl_distance": float(last["sl_distance"]),
            "tp_distance": float(last["tp_distance"]),
            "stop_loss": float(last["close"] + last["sl_distance"]),
            "take_profit": float(last["close"] - last["tp_distance"]),
            "rsi": float(last["rsi"]),
            "atr": float(last["atr"]),
            "timestamp": str(last["timestamp"]),
        }
    return None
