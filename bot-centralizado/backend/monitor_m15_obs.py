# -*- coding: utf-8 -*-
"""
Monitor M15 - MODO OBSERVACION (paper trading)
===============================================
NO ejecuta trades reales. Solo registra senales para validar la estrategia
durante 3-4 semanas antes de decidir si migrar o combinar con H1.

Parametros optimos hallados en backtest (15 dias, 72 combinaciones):
  EMA 3/8/21 | RSI 14 (35-65) | SL 0.5xATR / TP 1.5xATR | vol_mult=1.0
  Resultado backtest: ~206 trades/mes | WR 35.9% | PF 1.38 | MaxDD -15.3%

Log: m15_signal_log.csv
  Registra cada senal con entry/SL/TP teoricos para calcular resultado real despues.
"""
import os, sys
os.environ.setdefault('CAPITAL_MODE', 'REAL')
sys.path.insert(0, '.')

import csv
from datetime import datetime, timezone
from capital_client import CapitalClient
from strategy import StrategyConfig, calculate_indicators, generate_signals, get_position_size

# ── Parametros M15 optimos ─────────────────────────────────────────────────
M15_PARAMS = {
    "ema_fast": 3, "ema_slow": 8, "ema_long": 21,
    "rsi_period": 14, "rsi_overbought": 65.0, "rsi_oversold": 35.0,
    "atr_period": 14, "atr_sl_mult": 0.5, "atr_tp_mult": 1.5,
    "bb_period": 20, "bb_std": 2.0, "vol_sma_period": 50,
    "vol_mult": 1.0, "risk_pct": 1.0,
    "preset_name": "M15_OBS",
    "preset_description": "M15 observacion",
    "recommended_timeframe": "MINUTE_15",
}
EPIC     = 'GOLD'
RISK_PCT = 1.0
LOG_PATH = os.path.join(os.path.dirname(__file__), 'm15_signal_log.csv')

# ── Inicializar log si no existe ───────────────────────────────────────────
if not os.path.exists(LOG_PATH):
    with open(LOG_PATH, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'datetime_utc', 'epic', 'direction',
            'entry_price', 'sl', 'tp', 'rr',
            'size_teorico', 'riesgo_teorico_usd',
            'rsi', 'atr', 'ema_align',
            'resultado', 'pnl_teorico_usd', 'notas'
        ])

# ── Conexion y datos ───────────────────────────────────────────────────────
now_utc = datetime.now(timezone.utc)

client = CapitalClient()
if not client.login():
    print("ERROR: Login fallido")
    sys.exit(1)

bal       = client.get_balance()
equity    = bal['balance'] if bal else 250.0

df = client.get_prices(EPIC, 'MINUTE_15', 200)
if df is None or len(df) < 50:
    print("ERROR: Sin datos M15")
    sys.exit(1)

# ── Indicadores y senales ──────────────────────────────────────────────────
cfg = StrategyConfig(**M15_PARAMS)
df  = calculate_indicators(df, cfg)
df  = generate_signals(df, cfg)

cur  = df.iloc[-1]
prev = df.iloc[-2]

ema_bull = prev['ema_fast'] > prev['ema_slow'] and prev['ema_slow'] > prev['ema_long']
ema_bear = prev['ema_fast'] < prev['ema_slow'] and prev['ema_slow'] < prev['ema_long']
ema_align = "ALCISTA" if ema_bull else ("BAJISTA" if ema_bear else "MIXTA")

signal = None
if prev['buy_signal']:
    signal = 'BUY'
elif prev['sell_signal']:
    signal = 'SELL'

# ── Imprimir estado ────────────────────────────────────────────────────────
print("=" * 55)
print("AUREX | MONITOR M15 | " + EPIC + " | OBSERVACION")
print("Hora UTC: " + now_utc.strftime('%H:%M') + " | Equity: $" + str(round(equity, 2)))
print("=" * 55)
print("MERCADO M15")
print("  Precio : " + str(round(float(cur['close']), 2)))
print("  RSI    : " + str(round(float(prev['rsi']), 1)))
print("  ATR    : " + str(round(float(prev['atr']), 2)))
print("  EMA    : " + str(round(float(prev['ema_fast']), 2))
      + " / " + str(round(float(prev['ema_slow']), 2))
      + " / " + str(round(float(prev['ema_long']), 2))
      + "  [" + ema_align + "]")

if signal is None:
    print()
    print("SENYAL M15: Sin senal - esperando")
    print("=" * 55)
    sys.exit(0)

# ── Calcular niveles teoricos ──────────────────────────────────────────────
entry   = float(cur['close'])
sl_dist = float(prev['sl_distance'])
tp_dist = float(prev['tp_distance'])

if signal == 'BUY':
    sl = round(entry - sl_dist, 2)
    tp = round(entry + tp_dist, 2)
else:
    sl = round(entry + sl_dist, 2)
    tp = round(entry - tp_dist, 2)

rr   = round(tp_dist / sl_dist, 2) if sl_dist > 0 else 0
size = get_position_size(equity, sl_dist, RISK_PCT)

print()
print("SENYAL M15: " + signal + " [MODO OBSERVACION - NO SE EJECUTA]")
print("  Entry  : " + str(round(entry, 2)))
print("  SL     : " + str(sl) + " (dist: " + str(round(sl_dist, 2)) + " pts)")
print("  TP     : " + str(tp) + " (dist: " + str(round(tp_dist, 2)) + " pts)")
print("  R:R    : 1:" + str(rr))
print("  Size   : " + str(round(size, 4)) + " | Riesgo teorico: $" + str(round(sl_dist * size, 2)))
print("  >> Registrada en m15_signal_log.csv para seguimiento")
print("=" * 55)

# ── Registrar en log ───────────────────────────────────────────────────────
with open(LOG_PATH, 'a', newline='') as f:
    writer = csv.writer(f)
    writer.writerow([
        now_utc.strftime('%Y-%m-%d %H:%M'),
        EPIC, signal,
        round(entry, 2), sl, tp, rr,
        round(size, 4), round(sl_dist * size, 2),
        round(float(prev['rsi']), 1),
        round(float(prev['atr']), 2),
        ema_align,
        'PENDIENTE', '', 'Observacion M15 - sin ejecucion real'
    ])
