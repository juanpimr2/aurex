# -*- coding: utf-8 -*-
"""
Aurex F1.5 — Tests de estrategia: sizing, indicadores y senales.
Lo que toca dinero, primero. Datos sinteticos, sin red ni broker.
Uso: python -m pytest tests/ -q
"""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategy import (
    StrategyConfig, STRATEGY_PRESETS, get_position_size,
    calculate_indicators, generate_signals, get_latest_signal,
)


# ── Sizing (riesgo monetario) ───────────────────────────────────────────────

def test_sizing_basico():
    # equity 650, riesgo 2%, SL a 14.6 pts -> size = 13 / 14.6
    size = get_position_size(equity=650.0, sl_distance=14.6, risk_pct=2.0)
    assert abs(size - (650 * 0.02 / 14.6)) < 1e-9


def test_sizing_riesgo_monetario_es_exacto():
    # El riesgo real (size * sl_distance) debe igualar equity * pct
    for equity in (250.0, 650.0, 5000.0):
        for pct in (1.0, 2.0, 5.0):
            for sl in (5.0, 14.6, 99.65):
                size = get_position_size(equity, sl, pct)
                assert abs(size * sl - equity * pct / 100) < 1e-6


def test_sizing_sl_cero_o_negativo_devuelve_minimo():
    assert get_position_size(650.0, 0.0, 5.0) == 0.01
    assert get_position_size(650.0, -3.0, 5.0) == 0.01


def test_sizing_respeta_minimo_capital_com():
    # SL enorme con cuenta pequena -> size < 0.01 se eleva al minimo del broker
    assert get_position_size(100.0, 10000.0, 1.0) == 0.01


# ── Presets (proteccion contra cambios accidentales) ───────────────────────

def test_preset_swing_es_el_aprobado():
    """El preset SWING en produccion es el aprobado el 1-jul-2026:
    SL 2.0x / TP 3.5x (R:R 1:1.75), riesgo base 1.5 (override 5.0 en monitor).
    Si este test falla, alguien cambio la estrategia sin pasar por validacion."""
    p = STRATEGY_PRESETS['SWING']['params']
    assert p['atr_sl_mult'] == 2.0
    assert p['atr_tp_mult'] == 3.5
    assert p['ema_fast'] == 8 and p['ema_slow'] == 21 and p['ema_long'] == 50
    assert p['rsi_oversold'] == 35.0 and p['rsi_overbought'] == 65.0


def test_preset_scalp_parametros():
    p = STRATEGY_PRESETS['SCALP']['params']
    assert p['atr_sl_mult'] == 0.8
    assert p['atr_tp_mult'] == 2.0
    assert p['risk_pct'] == 1.0


# ── Indicadores y senales con datos sinteticos ──────────────────────────────

def _df_tendencia(n=120, start=4000.0, step=5.0, subida=True):
    """Serie con tendencia limpia y volumen constante."""
    sgn = 1 if subida else -1
    closes = [start + sgn * step * i for i in range(n)]
    return pd.DataFrame({
        'timestamp': pd.date_range('2026-01-01', periods=n, freq='D'),
        'open':  [c - sgn * step * 0.5 for c in closes],
        'high':  [c + step for c in closes],
        'low':   [c - step for c in closes],
        'close': closes,
        'volume': [1000.0] * n,
    })


def test_indicadores_columnas_y_atr_positivo():
    cfg = StrategyConfig()
    df = calculate_indicators(_df_tendencia(), cfg)
    for col in ('ema_fast', 'ema_slow', 'ema_long', 'rsi', 'atr', 'bb_upper', 'bb_lower'):
        assert col in df.columns
    assert (df['atr'].dropna() > 0).all()


def test_tendencia_alcista_alinea_emas():
    cfg = StrategyConfig()
    df = calculate_indicators(_df_tendencia(subida=True), cfg)
    last = df.iloc[-1]
    assert last['ema_fast'] > last['ema_slow'] > last['ema_long']


def test_sell_signal_no_aparece_en_tendencia_alcista():
    cfg = StrategyConfig()
    df = generate_signals(calculate_indicators(_df_tendencia(subida=True), cfg), cfg)
    assert not df['sell_signal'].fillna(False).any()


def test_buy_signal_no_aparece_en_tendencia_bajista():
    cfg = StrategyConfig()
    df = generate_signals(calculate_indicators(_df_tendencia(subida=False), cfg), cfg)
    assert not df['buy_signal'].fillna(False).any()


def test_sl_tp_distancias_respetan_multiplicadores():
    cfg = StrategyConfig()  # SL 2.0x, TP 3.5x tras el cambio aprobado
    df = generate_signals(calculate_indicators(_df_tendencia(), cfg), cfg)
    last = df.dropna(subset=['atr']).iloc[-1]
    assert abs(last['sl_distance'] - last['atr'] * 2.0) < 1e-9
    assert abs(last['tp_distance'] - last['atr'] * 3.5) < 1e-9


def test_get_latest_signal_usa_vela_cerrada_no_la_ultima():
    """Anti look-ahead: la senal debe salir de iloc[-2] (vela completa)."""
    cfg = StrategyConfig()
    df = _df_tendencia(subida=True)
    sig = get_latest_signal(df, cfg)
    if sig is not None:
        cerrada = df['close'].iloc[-2]
        assert abs(sig['entry_price'] - cerrada) < 1e-9


def test_senal_buy_estructura_completa():
    """En tendencia alcista moderada con RSI en zona, la senal BUY (si existe)
    trae SL bajo el precio y TP encima, con distancias coherentes."""
    cfg = StrategyConfig()
    # tendencia con retrocesos para mantener el RSI fuera de sobrecompra
    n = 150
    rng = np.random.default_rng(42)
    closes = 4000 + np.cumsum(rng.normal(1.2, 6.0, n))
    df = pd.DataFrame({
        'timestamp': pd.date_range('2026-01-01', periods=n, freq='D'),
        'open': closes - 1, 'high': closes + 8, 'low': closes - 8,
        'close': closes, 'volume': [1000.0] * n,
    })
    sig = get_latest_signal(df, cfg)
    if sig and sig['direction'] == 'BUY':
        assert sig['stop_loss'] < sig['entry_price'] < sig['take_profit']
        assert abs((sig['entry_price'] - sig['stop_loss']) - sig['sl_distance']) < 1e-6


# ── Parsing de eq_open en notas (auto-close) ───────────────────────────────

def _parse_eq_open(notas: str):
    """Copia exacta de la logica de parsing de monitor_scalp.auto_close_*."""
    eq_open = None
    for part in notas.split('|'):
        part = part.strip()
        if part.startswith('eq_open='):
            try:
                eq_open = float(part.split('=')[1])
            except Exception:
                pass
    return eq_open


def test_parse_eq_open_presente():
    assert _parse_eq_open('M15 REAL | eq_open=646.51') == 646.51


def test_parse_eq_open_ausente():
    assert _parse_eq_open('Trade SWING real abierto') is None


def test_parse_eq_open_corrupto_no_revienta():
    assert _parse_eq_open('x | eq_open=abc | y') is None
