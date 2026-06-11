# -*- coding: utf-8 -*-
"""
Monitor M15 - MODO REAL
========================
Executes real trades on Capital.com using the M15+H4 strategy.

Parameters : EMA 3/8/21 | RSI 14 (30-70) | SL 1.5xATR / TP 2.0xATR
Session    : 01:00-22:00 UTC (Asia + London + NY)
ATR        : dynamic filter (must be > SMA50 of own ATR)
NY filter  : 13:15-14:45 UTC blocked (anti-spike — under evaluation)
Cooldown   : 1.5h between same-direction trades
H4 filter  : blocks entry if H4 trend contradicts signal
SMC H4     : informational (Phase 1)

Logs: m15_signal_log.csv + SQLite aurex_trades.db
"""
import os
import sys
os.environ.setdefault('CAPITAL_MODE', 'REAL')
sys.path.insert(0, '.')

import csv
import json
from datetime import datetime, timezone

from capital_client import CapitalClient
from strategy import StrategyConfig, calculate_indicators, generate_signals, get_position_size, calculate_supertrend
from db import log_trade_open, init_db

init_db()

# ── Parameters ────────────────────────────────────────────────────────────
M15_PARAMS = {
    "ema_fast": 3, "ema_slow": 8, "ema_long": 21,
    "rsi_period": 14, "rsi_overbought": 70.0, "rsi_oversold": 30.0,
    "atr_period": 14, "atr_sl_mult": 1.5, "atr_tp_mult": 2.0,
    "bb_period": 20, "bb_std": 2.0, "vol_sma_period": 50,
    "vol_mult": 1.0, "risk_pct": 1.0,
    "preset_name": "M15_REAL",
    "preset_description": "M15 real trading",
    "recommended_timeframe": "MINUTE_15",
}
EPIC          = 'GOLD'
RISK_PCT      = 2.0
LOG_PATH      = os.path.join(os.path.dirname(__file__), 'm15_signal_log.csv')
STATE_PATH    = os.path.join(os.path.dirname(__file__), 'm15_trade_state.json')
COOLOFF_HOURS = 1.5

# Session window: 01:00-22:00 UTC
SESION_INICIO = 1.0
SESION_FIN    = 22.0

# NY open filter: 13:15-14:45 UTC (under evaluation — disable after data review)
NY_OPEN_START = 13.25
NY_OPEN_END   = 14.75

# ATR dynamic filter: ATR must exceed this multiple of its own SMA50
ATR_MULT_MIN  = 1.0

# ── Init log ──────────────────────────────────────────────────────────────
if not os.path.exists(LOG_PATH):
    with open(LOG_PATH, 'w', newline='') as f:
        csv.writer(f).writerow([
            'datetime_utc', 'epic', 'direction',
            'entry_price', 'sl', 'tp', 'rr',
            'size_teorico', 'riesgo_teorico_usd',
            'rsi', 'atr', 'ema_align',
            'resultado', 'pnl_teorico_usd', 'notas'
        ])

# ── Auto-cierre M15: detectar posiciones OPEN que cerraron en broker ──────
def auto_close_m15_trades(positions, equity_now, now_str):
    if not os.path.exists(LOG_PATH):
        return

    with open(LOG_PATH, newline='') as f:
        rows = list(csv.DictReader(f))

    open_idxs = [i for i, r in enumerate(rows)
                 if str(r.get('resultado', '')).upper().startswith('OPEN')]
    if not open_idxs:
        return

    active = set()
    for p in positions:
        active.add((str(p.get('epic', '')).upper(), p.get('direction', '')))

    state_eq, state_dir = None, None
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, 'r') as _sf:
                _st = json.load(_sf)
            state_eq  = float(_st.get('equity_before') or 0) or None
            state_dir = _st.get('direction')
        except Exception:
            pass

    changed = False
    for idx in open_idxs:
        row = rows[idx]
        key = (str(row.get('epic', '')).upper(), row.get('direction', ''))
        if key in active:
            continue

        notas = row.get('notas', '') or ''
        eq_open = None
        for part in notas.split('|'):
            part = part.strip()
            if part.startswith('eq_open='):
                try:
                    eq_open = float(part.split('=')[1])
                except Exception:
                    pass
        if eq_open is None and state_eq and state_dir == row.get('direction'):
            eq_open = state_eq

        try:
            sl_price  = float(row.get('sl')           or 0)
            tp_price  = float(row.get('tp')           or 0)
            entry     = float(row.get('entry_price')  or 0)
            size      = float(row.get('size_teorico') or 0)
            direction = row.get('direction', '')

            if direction == 'BUY':
                expected_tp_pnl = round((tp_price - entry) * size, 2)
                expected_sl_pnl = round((entry - sl_price) * size, 2)
            else:
                expected_tp_pnl = round((entry - tp_price) * size, 2)
                expected_sl_pnl = round((sl_price - entry) * size, 2)

            if eq_open is not None:
                pnl = round(equity_now - eq_open, 2)
                if pnl >= 0:
                    result = 'TP'
                    if expected_tp_pnl > 0 and abs(pnl - expected_tp_pnl) < expected_tp_pnl * 0.4:
                        pnl = expected_tp_pnl
                else:
                    result = 'SL'
                    if expected_sl_pnl > 0 and abs(pnl + expected_sl_pnl) < expected_sl_pnl * 0.4:
                        pnl = -expected_sl_pnl
            else:
                result = 'CERRADO'
                pnl    = 0.0
        except Exception:
            result = 'CERRADO'
            pnl    = 0.0

        rows[idx]['resultado']       = result
        rows[idx]['pnl_teorico_usd'] = pnl
        rows[idx]['notas']           = notas + ' | AUTO-CERRADO ' + result + ' ' + now_str
        changed = True
        print("  [AUTO-CIERRE M15] " + row.get('direction', '') + " " + row.get('epic', '')
              + " -> " + result + " | P&L: $" + str(pnl))

    if changed:
        fieldnames = list(rows[0].keys())
        with open(LOG_PATH, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print("  M15 log actualizado automaticamente.")


# ── Connect ───────────────────────────────────────────────────────────────
now_utc = datetime.now(timezone.utc)
hora_utc = now_utc.hour + now_utc.minute / 60.0

client = CapitalClient()
if not client.login():
    print("ERROR: Login fallido")
    sys.exit(1)

bal    = client.get_balance()
equity = bal['balance'] if bal else 250.0

# ── Auto-cierre antes de evaluar señal ────────────────────────────────────
open_pos_check = client.get_positions()
auto_close_m15_trades(open_pos_check, equity, now_utc.strftime('%Y-%m-%d %H:%M'))

df = client.get_prices(EPIC, 'MINUTE_15', 200)
if df is None or len(df) < 50:
    print("ERROR: Sin datos M15")
    sys.exit(1)

# ── H1 and H4 trends ──────────────────────────────────────────────────────
from strategy import StrategyConfig as SC
_tf_cfg = SC()

df_h1 = client.get_prices(EPIC, 'HOUR', 50)
h1_trend = "MIXTA"
if df_h1 is not None and len(df_h1) >= 10:
    df_h1  = calculate_indicators(df_h1, _tf_cfg)
    h1last = df_h1.iloc[-1]
    h1_bull = h1last['ema_fast'] > h1last['ema_slow'] and h1last['ema_slow'] > h1last['ema_long']
    h1_bear = h1last['ema_fast'] < h1last['ema_slow'] and h1last['ema_slow'] < h1last['ema_long']
    h1_trend = "ALCISTA" if h1_bull else ("BAJISTA" if h1_bear else "MIXTA")

df_h4 = client.get_prices(EPIC, 'HOUR_4', 100)
h4_trend   = "MIXTA"
h4_st_bias = "NEUTRAL"   # SuperTrend H4 bias (primary filter)
if df_h4 is not None and len(df_h4) >= 20:
    df_h4  = calculate_indicators(df_h4, _tf_cfg)
    df_h4  = calculate_supertrend(df_h4, period=10, multiplier=3.0)
    h4last = df_h4.iloc[-1]
    h4_bull = h4last['ema_fast'] > h4last['ema_slow'] and h4last['ema_slow'] > h4last['ema_long']
    h4_bear = h4last['ema_fast'] < h4last['ema_slow'] and h4last['ema_slow'] < h4last['ema_long']
    h4_trend   = "ALCISTA" if h4_bull else ("BAJISTA" if h4_bear else "MIXTA")
    h4_st_bias = "ALCISTA" if int(h4last['st_direction']) == 1 else "BAJISTA"

# ── SMC H4: Break of Structure (informational — Phase 1) ─────────────────
smc_bias  = "N/A"
smc_event = ""
try:
    from smc_filters import smc_summary
    _smc = smc_summary(df_h4, None, 0.0)
    smc_bias  = _smc['h4_bias']
    smc_event = _smc['h4_event']
except Exception:
    pass

# ── Indicators and signals ────────────────────────────────────────────────
cfg = StrategyConfig(**M15_PARAMS)
df  = calculate_indicators(df, cfg)
df  = generate_signals(df, cfg)

cur  = df.iloc[-1]
prev = df.iloc[-2]

ema_bull  = prev['ema_fast'] > prev['ema_slow'] and prev['ema_slow'] > prev['ema_long']
ema_bear  = prev['ema_fast'] < prev['ema_slow'] and prev['ema_slow'] < prev['ema_long']
ema_align = "ALCISTA" if ema_bull else ("BAJISTA" if ema_bear else "MIXTA")

# ── Print market state ────────────────────────────────────────────────────
print("=" * 55)
print("AUREX | MONITOR M15 | " + EPIC + " | REAL")
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
print("  H1     : " + h1_trend)
print("  H4 EMA : " + h4_trend)
print("  H4 ST  : " + h4_st_bias + "  [SuperTrend 10,3]")
print("  SMC H4 : " + smc_bias + (" " + smc_event if smc_event else ""))

# ── Check open position — manage trailing stop ────────────────────────────
open_pos  = client.get_positions()
gold_pos  = [p for p in open_pos if p.get('epic') == EPIC]

if gold_pos:
    p = gold_pos[0]
    entry_p  = p.get('entry_price') or 0
    sl_p     = p.get('stop_loss') or 0
    tp_p     = p.get('take_profit') or 0
    pnl_p    = p.get('profit_loss') or 0
    size_p   = p.get('size') or 0
    direc_p  = p.get('direction', '')
    deal_p   = p.get('deal_id')

    dist_tp = abs(tp_p - entry_p) if tp_p else 0
    pct_tp  = (abs(pnl_p) / (dist_tp * size_p) * 100) if (dist_tp and size_p and pnl_p > 0) else 0

    print()
    print("POSICION ABIERTA: " + direc_p + " x" + str(size_p)
          + " | Entry: " + str(entry_p)
          + " | SL: " + str(sl_p) + " | TP: " + str(tp_p))
    print("  PnL: $" + str(round(pnl_p, 2)) + " | % hacia TP: " + str(round(pct_tp, 1)) + "%")

    # Move SL to breakeven when 50%+ toward TP
    if pct_tp >= 50 and deal_p:
        breakeven = round(entry_p, 2)
        already_safe = (
            (direc_p == 'BUY'  and sl_p >= breakeven) or
            (direc_p == 'SELL' and sl_p <= breakeven and sl_p > 0)
        )
        if not already_safe:
            ok = client.modify_position(deal_p, stop_loss=breakeven)
            print("  [TRAILING] SL -> breakeven " + str(breakeven)
                  + " | " + ("OK" if ok else "ERROR"))
        else:
            print("  [TRAILING] Ya en breakeven o mejor")

    print()
    print("SENYAL M15: Posicion abierta — sin nueva entrada")
    print("=" * 55)
    sys.exit(0)

# ── Signal ────────────────────────────────────────────────────────────────
signal = None
if prev['buy_signal']:
    signal = 'BUY'
elif prev['sell_signal']:
    signal = 'SELL'

if signal is None:
    print()
    print("SENYAL M15: Sin senal - esperando")
    print("=" * 55)
    sys.exit(0)

# ── Filter: session window ────────────────────────────────────────────────
if hora_utc < SESION_INICIO or hora_utc >= SESION_FIN:
    print()
    print("SENYAL M15: " + signal + " BLOQUEADA — fuera de sesion (01:00-22:00 UTC)")
    print("=" * 55)
    sys.exit(0)

# ── Filter: NY open window ────────────────────────────────────────────────
if NY_OPEN_START <= hora_utc < NY_OPEN_END:
    print()
    print("SENYAL M15: " + signal + " BLOQUEADA — ventana NY open (13:15-14:45 UTC)")
    print("=" * 55)
    sys.exit(0)

# ── Filter: dynamic ATR (must exceed SMA50 of ATR) ───────────────────────
atr_val = float(prev['atr'])
try:
    atr_sma50   = float(df['atr'].rolling(50, min_periods=20).mean().iloc[-2])
    atr_blocked = atr_val < atr_sma50 * ATR_MULT_MIN
    atr_ref_str = "SMA50=" + str(round(atr_sma50, 2))
except Exception:
    atr_blocked = False
    atr_ref_str = "SMA50=N/A"

if atr_blocked:
    print()
    print("SENYAL M15: " + signal + " BLOQUEADA — ATR bajo ("
          + str(round(atr_val, 2)) + " < " + atr_ref_str + ")")
    print("=" * 55)
    sys.exit(0)

# ── Filter: H4 SuperTrend (primary directional filter) ───────────────────
# SuperTrend on H4 has WR 86.7% / PF 8.67 on 230 days of GOLD data.
# This is the strongest filter in the system — only trade WITH the H4 ST bias.
if h4_st_bias != "NEUTRAL":
    if (signal == 'BUY' and h4_st_bias == 'BAJISTA') or (signal == 'SELL' and h4_st_bias == 'ALCISTA'):
        print()
        print("SENYAL M15: " + signal + " BLOQUEADA — H4 SuperTrend " + h4_st_bias + " contradice entrada")
        print("=" * 55)
        sys.exit(0)

# ── Filter: H4 EMA trend (secondary confirmation) ────────────────────────
if (signal == 'BUY' and h4_trend == 'BAJISTA') or (signal == 'SELL' and h4_trend == 'ALCISTA'):
    print()
    print("SENYAL M15: " + signal + " BLOQUEADA — H4 EMA " + h4_trend + " contradice entrada")
    print("=" * 55)
    sys.exit(0)

# ── Filter: cooldown (1.5h between same-direction trades) ────────────────
if os.path.exists(STATE_PATH):
    try:
        with open(STATE_PATH, 'r') as _sf:
            _state = json.load(_sf)
        _last_dir = _state.get('direction')
        _last_ts  = datetime.fromisoformat(_state.get('timestamp', '2000-01-01T00:00:00+00:00'))
        _elapsed  = (now_utc - _last_ts).total_seconds() / 3600
        if _last_dir == signal and _elapsed < COOLOFF_HOURS:
            _remaining = round(COOLOFF_HOURS - _elapsed, 1)
            print()
            print("SENYAL M15: " + signal + " BLOQUEADA — cooldown activo ("
                  + str(round(_elapsed, 1)) + "h/" + str(COOLOFF_HOURS) + "h, faltan "
                  + str(_remaining) + "h)")
            print("=" * 55)
            sys.exit(0)
    except Exception:
        pass

# ── Calculate levels ──────────────────────────────────────────────────────
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

# ── SMC: confluence check with entry and signal ───────────────────────────
smc_ob_warn  = False
smc_fvg_conf = False
try:
    from smc_filters import smc_summary
    _smc2 = smc_summary(df_h4, df, entry, signal)
    smc_ob_warn  = _smc2['ob_warning']
    smc_fvg_conf = _smc2['fvg_confluence']
except Exception:
    pass

print()
print("SENYAL M15: " + signal)
print("  Entry  : " + str(round(entry, 2)))
print("  SL     : " + str(sl) + " (dist: " + str(round(sl_dist, 2)) + " pts)")
print("  TP     : " + str(tp) + " (dist: " + str(round(tp_dist, 2)) + " pts)")
print("  R:R    : 1:" + str(rr))
print("  Size   : " + str(round(size, 4)) + " | Riesgo: $" + str(round(sl_dist * size, 2)))
print("  SMC H4 : " + smc_bias + (" " + smc_event if smc_event else "")
      + (" | OB_WARN" if smc_ob_warn else "")
      + (" | FVG_OK"  if smc_fvg_conf else ""))

# ── Open position ─────────────────────────────────────────────────────────
print()
print("Abriendo posicion...")
deal_id    = None
final_size = None
for attempt_size in [round(size, 2), 0.05, 0.01]:
    deal_id = client.open_position(
        epic=EPIC, direction=signal, size=attempt_size,
        stop_loss=sl, take_profit=tp
    )
    if deal_id:
        final_size = attempt_size
        print("ABIERTA OK | Deal: " + deal_id + " | Size: " + str(attempt_size)
              + " | Riesgo real: $" + str(round(sl_dist * attempt_size, 2)))
        try:
            with open(STATE_PATH, 'w') as _sf:
                json.dump({
                    'timestamp': now_utc.isoformat(),
                    'direction': signal,
                    'equity_before': round(equity, 2),
                    'deal_id': deal_id,
                }, _sf)
        except Exception:
            pass
        break
    print("  Size " + str(attempt_size) + " rechazado, probando menor...")

if not deal_id:
    print("ERROR: No se pudo abrir la posicion.")

print("=" * 55)

# ── Log ───────────────────────────────────────────────────────────────────
estado = ('OPEN | Deal:' + deal_id) if deal_id else 'ERROR_OPEN'
_ts    = now_utc.strftime('%Y-%m-%d %H:%M')
_sz    = round(final_size or size, 4)
_rsk   = round(sl_dist * (final_size or size), 2)

with open(LOG_PATH, 'a', newline='') as f:
    csv.writer(f).writerow([
        _ts, EPIC, signal,
        round(entry, 2), sl, tp, rr,
        _sz, _rsk,
        round(float(prev['rsi']), 1),
        round(float(prev['atr']), 2),
        ema_align,
        estado, '', 'M15 REAL | eq_open=' + str(round(equity, 2))
    ])

log_trade_open(
    datetime_utc  = _ts,
    epic          = EPIC,
    source        = 'M15',
    direction     = signal,
    entry_price   = round(entry, 2),
    sl            = sl,
    tp            = tp,
    rr            = rr,
    size          = _sz,
    riesgo_usd    = _rsk,
    rsi           = round(float(prev['rsi']), 1),
    atr           = round(float(prev['atr']), 2),
    ema_align     = ema_align,
    h1_trend      = h1_trend,
    h4_trend      = h4_trend,
    deal_id       = deal_id,
    equity_before = round(equity, 2),
    notas         = 'M15 REAL',
)
