# -*- coding: utf-8 -*-
"""
Monitor SWING DAY - Aurex
==========================
Cazatendencias de largo plazo sobre GOLD en timeframe diario.
Captura movimientos de $30-150 en dias/semanas.

MODO ACTUAL: OBSERVACION (paper trading)
  - No ejecuta trades reales hasta validacion de 2-3 semanas.
  - Log en swing_signal_log.csv

Estrategia SWING (backtest DAY 500 velas, Aug2024-Mar2026):
  EMA 8/21/50 | RSI 14 (35-65) | SL 2xATR | TP 2.5xATR
  Win Rate: 46.7% | PF: 2.26 | Return: +441% | MaxDD: 26.9%

Confirmacion: H4 como filtro de entrada (mismo rol que H4 en SCALP H1)
"""
import os, sys
os.environ.setdefault('CAPITAL_MODE', 'REAL')
sys.path.insert(0, '.')

import csv
from datetime import datetime, timezone
from capital_client import CapitalClient
from strategy import StrategyConfig, STRATEGY_PRESETS, calculate_indicators, generate_signals, get_position_size

EPIC     = 'GOLD'
RISK_PCT = 1.0
LOG_PATH = os.path.join(os.path.dirname(__file__), 'swing_signal_log.csv')
MODO_REAL = True    # Activado 17 Apr 2026 — backtest 500 velas (WR 46.7%, PF 2.26, +441%)

# ── Inicializar log si no existe ───────────────────────────────────────────
if not os.path.exists(LOG_PATH):
    with open(LOG_PATH, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'datetime_utc', 'epic', 'direction',
            'entry_price', 'sl', 'tp', 'rr',
            'size_teorico', 'riesgo_teorico_usd',
            'rsi_day', 'atr_day', 'ema_align_day',
            'h4_trend', 'rsi_h4',
            'resultado', 'pnl_teorico_usd', 'notas'
        ])

now_utc = datetime.now(timezone.utc)
friday_close = (datetime.now().weekday() == 4 and datetime.now().hour >= 17)

client = CapitalClient()
if not client.login():
    print("ERROR: Login fallido")
    sys.exit(1)

bal       = client.get_balance()
positions = client.get_positions()
equity    = bal['balance']   if bal else 250.0
available = bal['available'] if bal else 250.0
pnl_open  = bal['profit_loss'] if bal else 0.0

print("=" * 60)
print("AUREX | MONITOR SWING DAY | " + EPIC + " | " + ("OBSERVACION" if not MODO_REAL else "REAL"))
print("Hora UTC: " + now_utc.strftime('%Y-%m-%d %H:%M'))
print("=" * 60)
print("CUENTA")
print("  Balance    : $" + str(round(equity, 2)))
print("  Disponible : $" + str(round(available, 2)))
print("  PnL abierto: $" + str(round(pnl_open, 2)))
print("  Posiciones : " + str(len(positions)))

# ── Posiciones abiertas ────────────────────────────────────────────────────
if positions:
    print()
    print("POSICIONES ABIERTAS")
    for p in positions:
        entry  = p.get('entry_price') or 0
        sl     = p.get('stop_loss')   or 0
        tp     = p.get('take_profit') or 0
        pnl    = p.get('profit_loss') or 0
        direc  = p.get('direction', '?')
        size   = p.get('size') or 0
        dist_sl = abs(entry - sl) if sl else 0
        dist_tp = abs(tp - entry) if tp else 0
        pct_tp  = (abs(pnl) / (dist_tp * size) * 100) if (dist_tp and size and pnl > 0) else 0
        print("  " + str(p.get('epic','')) + " " + direc + " x" + str(size))
        print("  Entry:" + str(entry) + " SL:" + str(sl) + " TP:" + str(tp))
        print("  PnL: $" + str(round(pnl,2)) + " | % hacia TP: " + str(round(pct_tp,1)) + "%")

# ── Datos de mercado ───────────────────────────────────────────────────────
df_day = client.get_prices(EPIC, 'DAY',    150)
df_h4  = client.get_prices(EPIC, 'HOUR_4',  80)

if df_day is None or df_h4 is None:
    print("ERROR: Sin datos de mercado")
    sys.exit(1)

# DAY — preset SWING
swing_cfg = StrategyConfig(**STRATEGY_PRESETS['SWING']['params'])
df_day = calculate_indicators(df_day, swing_cfg)
df_day = generate_signals(df_day, swing_cfg)

# H4 — preset SWING para confirmacion de tendencia
df_h4 = calculate_indicators(df_h4, swing_cfg)
df_h4 = generate_signals(df_h4, swing_cfg)

day_cur  = df_day.iloc[-1]
day_prev = df_day.iloc[-2]
h4_last  = df_h4.iloc[-1]

# Tendencia DAY (EMAs)
day_bull = day_prev['ema_fast'] > day_prev['ema_slow'] and day_prev['ema_slow'] > day_prev['ema_long']
day_bear = day_prev['ema_fast'] < day_prev['ema_slow'] and day_prev['ema_slow'] < day_prev['ema_long']
day_trend = "ALCISTA" if day_bull else ("BAJISTA" if day_bear else "MIXTA/LATERAL")

# Tendencia H4 (confirmacion)
h4_bull = h4_last['ema_fast'] > h4_last['ema_slow'] and h4_last['ema_slow'] > h4_last['ema_long']
h4_bear = h4_last['ema_fast'] < h4_last['ema_slow'] and h4_last['ema_slow'] < h4_last['ema_long']
h4_trend = "ALCISTA" if h4_bull else ("BAJISTA" if h4_bear else "MIXTA/LATERAL")

# Precio actual (usar cierre de vela H4 mas reciente como referencia)
current_price = float(h4_last['close'])
rsi_day = float(day_prev['rsi'])
atr_day = float(day_prev['atr'])
rsi_h4  = float(h4_last['rsi'])

print()
print("ANALISIS MULTI-TIMEFRAME")
print("  Precio actual : $" + str(round(current_price, 2)))
print()
print("  DAY | Tend: " + day_trend
      + " | RSI: " + str(round(rsi_day, 1))
      + " | ATR: " + str(round(atr_day, 2)))
print("  EMA DAY: " + str(round(float(day_prev['ema_fast']), 2))
      + " / " + str(round(float(day_prev['ema_slow']), 2))
      + " / " + str(round(float(day_prev['ema_long']), 2)))
print("  BB DAY : " + str(round(float(day_prev['bb_lower']), 2))
      + " - " + str(round(float(day_prev['bb_upper']), 2)))
print()
print("  H4  | Tend: " + h4_trend
      + " | RSI: " + str(round(rsi_h4, 1)))

# Alineacion multi-timeframe
print()
if day_bull and h4_bull:
    mtf_align = "ALCISTA CONFIRMADA (DAY + H4 alineados)"
elif day_bear and h4_bear:
    mtf_align = "BAJISTA CONFIRMADA (DAY + H4 alineados)"
elif day_bull and not h4_bull:
    mtf_align = "ALCISTA DAY — H4 aun no confirma"
elif day_bear and not h4_bear:
    mtf_align = "BAJISTA DAY — H4 aun no confirma"
else:
    mtf_align = "SIN TENDENCIA CLARA (lateral)"
print("  MTF Alineacion: " + mtf_align)

# ── Senal DAY ─────────────────────────────────────────────────────────────
signal = None
if day_prev['buy_signal']:
    signal = 'BUY'
elif day_prev['sell_signal']:
    signal = 'SELL'

print()
if signal is None:
    print("SENYAL SWING: Sin senal - esperando")
    print()
    print("  El SCALP H1 puede operar con normalidad.")
    print("=" * 60)
    sys.exit(0)

print("SENYAL SWING: " + signal)

# ── Filtro viernes ─────────────────────────────────────────────────────────
if friday_close:
    print("  BLOQUEADA: Viernes despues de las 17:00 — cierre de semana")
    print("=" * 60)
    sys.exit(0)

# ── Filtro H4: confirmacion de tendencia ──────────────────────────────────
if (signal == 'BUY' and h4_bear) or (signal == 'SELL' and h4_bull):
    print("  FILTRO H4: " + h4_trend + " contradice " + signal)
    print("  -> Senal DAY detectada pero H4 no confirma. Esperando alineacion.")
    print()
    print("  El SCALP H1 puede operar con normalidad.")
    print("=" * 60)
    sys.exit(0)

# ── Calcular niveles ───────────────────────────────────────────────────────
sl_dist = float(day_prev['sl_distance'])
tp_dist = float(day_prev['tp_distance'])

if signal == 'BUY':
    sl = round(current_price - sl_dist, 2)
    tp = round(current_price + tp_dist, 2)
else:
    sl = round(current_price + sl_dist, 2)
    tp = round(current_price - tp_dist, 2)

rr   = round(tp_dist / sl_dist, 2) if sl_dist > 0 else 0
size = get_position_size(equity, sl_dist, RISK_PCT)

print("  Entry : $" + str(round(current_price, 2)))
print("  SL    : $" + str(sl) + " (dist: " + str(round(sl_dist, 2)) + " pts — " + str(round(sl_dist/atr_day, 1)) + "x ATR)")
print("  TP    : $" + str(tp) + " (dist: " + str(round(tp_dist, 2)) + " pts — " + str(round(tp_dist/atr_day, 1)) + "x ATR)")
print("  R:R   : 1:" + str(rr))
print("  Size  : " + str(round(size, 4)) + " | Riesgo: $" + str(round(sl_dist * size, 2)))
print("  H4    : " + h4_trend + " -> Confirmado")

if not MODO_REAL:
    print()
    print("  [OBSERVACION] Senal registrada en swing_signal_log.csv")
    print("  -> No se abre trade real. Activar MODO_REAL=True tras validacion.")
    print()
    print("  PRIORIDAD SWING: Registrada. SCALP H1 puede operar en paralelo.")
else:
    # ── Abrir posicion real ────────────────────────────────────────────────
    print()
    print("Abriendo posicion SWING automaticamente...")
    deal_id = None
    for attempt_size in [round(size, 2), 0.05, 0.01]:
        deal_id = client.open_position(
            epic=EPIC, direction=signal, size=attempt_size,
            stop_loss=sl, take_profit=tp
        )
        if deal_id:
            print("ABIERTA OK | Deal: " + deal_id + " | Size: " + str(attempt_size))
            break
        print("  Size " + str(attempt_size) + " rechazado, probando menor...")

# ── Registrar en log ───────────────────────────────────────────────────────
notas = ("Observacion SWING - sin ejecucion real" if not MODO_REAL
         else "Trade SWING real abierto")
with open(LOG_PATH, 'a', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow([
        now_utc.strftime('%Y-%m-%d %H:%M'),
        EPIC, signal,
        round(current_price, 2), sl, tp, rr,
        round(size, 4), round(sl_dist * size, 2),
        round(rsi_day, 1), round(atr_day, 2), day_trend,
        h4_trend, round(rsi_h4, 1),
        'PENDIENTE', '', notas
    ])

print()
print("=" * 60)
