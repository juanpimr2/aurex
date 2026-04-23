# -*- coding: utf-8 -*-
"""
Monitor SCALP H1 - Aurex
Ejecucion automatica con salvaguardas de riesgo.

Salvaguardas:
  0. Filtro horario: 24/5, viernes cierra a las 17:00 hora Madrid
  1. Conflicto H4: si H4 contradice H1, NO opera
  2. No duplicar direccion en el mismo epic
  3. Max riesgo abierto: 5% del equity simultaneo
  4. Pausa por drawdown abierto: > 10% equity
  5. Stop diario: si P&L del dia < -5% del equity, parar
  6. Cooling-off tras SL: si hubo SL hoy mismo epic/dir, exigir RSI
     neutral (35-65) y EMAs alineadas antes de re-entrar
  7. SL + TP siempre fijados al abrir

Funciones automaticas:
  - Auto-cierre: detecta cuando trades OPEN cierran en broker y actualiza log
  - Trailing stop: mueve SL a breakeven cuando posicion alcanza 50%+ del TP
"""
import os, sys
os.environ.setdefault('CAPITAL_MODE', 'REAL')
sys.path.insert(0, '.')

import csv
from datetime import datetime, timezone
from capital_client import CapitalClient
from strategy import StrategyConfig, STRATEGY_PRESETS, calculate_indicators, generate_signals, get_position_size

RISK_PCT        = 1.0    # % del equity por trade
MAX_RISK_OPEN   = 5.0    # % maximo del equity en riesgo simultaneo
MAX_DD_PCT      = 10.0   # % max drawdown abierto antes de pausar
MAX_DD_DAY_PCT  = 5.0    # % max perdida diaria antes de parar
EPIC            = 'GOLD'
LOG_PATH        = os.path.join(os.path.dirname(__file__), 'trade_log.csv')


# ── Auto-cierre: detectar trades OPEN que cerraron en broker ───────────────
def auto_close_open_trades(positions, equity_now, now_str):
    """
    Compara entradas OPEN del log con posiciones activas del broker.
    Si una entrada OPEN ya no esta en el broker -> cerro. Actualiza log.
    """
    if not os.path.exists(LOG_PATH):
        return

    with open(LOG_PATH, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))

    open_idxs = [i for i, r in enumerate(rows) if r.get('result', '').upper() == 'OPEN']
    if not open_idxs:
        return

    # Posiciones activas en broker (epic+direccion)
    active = set()
    for p in positions:
        active.add((str(p.get('epic', '')).upper(), p.get('direction', '')))

    changed = False
    for idx in open_idxs:
        row = rows[idx]
        key = (str(row.get('epic', '')).upper(), row.get('direction', ''))
        if key in active:
            continue  # Sigue abierto en broker

        # Ya no esta en broker -> cerro
        try:
            balance_open = float(row.get('balance_after') or equity_now)
        except Exception:
            balance_open = equity_now

        pnl = round(equity_now - balance_open, 2)

        # Determinar SL o TP usando los niveles guardados
        try:
            sl_price  = float(row.get('sl')    or 0)
            tp_price  = float(row.get('tp')    or 0)
            entry     = float(row.get('entry') or 0)
            size      = float(row.get('size')  or 0)
            expected_sl_pnl = round(abs(entry - sl_price) * size, 2) if sl_price else 0
            expected_tp_pnl = round(abs(tp_price - entry) * size, 2) if tp_price else 0

            if pnl >= 0:
                result = 'TP'
                pnl = expected_tp_pnl if (expected_tp_pnl > 0 and
                      abs(pnl - expected_tp_pnl) < expected_tp_pnl * 0.4) else pnl
            else:
                result = 'SL'
                pnl = -expected_sl_pnl if (expected_sl_pnl > 0 and
                      abs(pnl + expected_sl_pnl) < expected_sl_pnl * 0.4) else pnl
        except Exception:
            result = 'TP' if pnl > 0 else 'SL'

        rows[idx]['pnl_usd']      = pnl
        rows[idx]['result']       = result
        rows[idx]['balance_after'] = round(equity_now, 2)
        old_notes = rows[idx].get('notes', '') or ''
        rows[idx]['notes'] = old_notes + ' | AUTO-CERRADO ' + result + ' ' + now_str
        changed = True
        print("  [AUTO-CIERRE] " + row.get('direction', '') + " " + row.get('epic', '')
              + " -> " + result + " | P&L: $" + str(pnl))

    if changed:
        fieldnames = list(rows[0].keys())
        with open(LOG_PATH, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print("  Log actualizado automaticamente.")


# ── Trailing stop: mover SL a breakeven al 50%+ del TP ────────────────────
def apply_trailing_stop(client, positions):
    """
    Para cada posicion con P&L >= 50% del camino al TP,
    mueve el SL al precio de entrada (breakeven).
    """
    for p in positions:
        entry   = p.get('entry_price') or 0
        sl      = p.get('stop_loss')   or 0
        tp      = p.get('take_profit') or 0
        pnl     = p.get('profit_loss') or 0
        size    = p.get('size')        or 0
        deal_id = p.get('deal_id')
        direc   = p.get('direction', '')

        if not (entry and tp and deal_id):
            continue

        dist_tp = abs(tp - entry)
        if dist_tp == 0 or size == 0:
            continue

        pct_tp = (abs(pnl) / (dist_tp * size) * 100) if pnl > 0 else 0

        if pct_tp >= 50:
            breakeven = round(entry, 2)
            already_safe = (
                (direc == 'BUY'  and sl >= breakeven) or
                (direc == 'SELL' and sl <= breakeven and sl > 0)
            )
            if not already_safe:
                ok = client.modify_position(deal_id, stop_loss=breakeven)
                if ok:
                    print("  [TRAILING STOP] SL -> breakeven $" + str(breakeven)
                          + " | " + direc + " " + str(p.get('epic', ''))
                          + " | " + str(round(pct_tp, 1)) + "% TP alcanzado ✓")
                else:
                    print("  [TRAILING STOP] ERROR al mover SL de " + direc
                          + " " + str(p.get('epic', '')) + " — verificar manualmente")
            else:
                print("  [TRAILING STOP] Ya protegido (SL en breakeven o mejor)")


# ── Inicio ─────────────────────────────────────────────────────────────────
now_utc   = datetime.now(timezone.utc)
now_local = datetime.now()
friday_close = (now_local.weekday() == 4 and now_local.hour >= 17)

client = CapitalClient()
if not client.login():
    print("ERROR: Login fallido")
    sys.exit(1)

bal       = client.get_balance()
positions = client.get_positions()

equity    = bal['balance']    if bal else 250.0
available = bal['available']  if bal else 250.0
pnl_open  = bal['profit_loss'] if bal else 0.0

# ── Auto-cierre antes de mostrar estado ────────────────────────────────────
auto_close_open_trades(positions, equity, now_utc.strftime('%Y-%m-%d %H:%M'))

session_label = "CIERRE SEMANA" if friday_close else "ACTIVA"
print("=" * 55)
print("AUREX | MONITOR SCALP H1 | " + EPIC)
print("Hora UTC: " + now_utc.strftime('%H:%M') + " | Sesion: " + session_label)
print("=" * 55)
print("CUENTA")
print("  Balance    : $" + str(round(equity, 2)))
print("  Disponible : $" + str(round(available, 2)))
print("  PnL abierto: $" + str(round(pnl_open, 2)))
print("  Posiciones : " + str(len(positions)))

# ── Posiciones abiertas + trailing stop ────────────────────────────────────
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
        print("  " + str(p.get('epic', '')) + " " + direc + " x" + str(size))
        print("  Entry:" + str(entry) + " SL:" + str(sl) + " TP:" + str(tp))
        print("  PnL: $" + str(round(pnl, 2)) + " | % hacia TP: " + str(round(pct_tp, 1)) + "%")
        if pct_tp >= 50:
            print("  >> Activando trailing stop a breakeven...")

    # Aplicar trailing stop automatico
    apply_trailing_stop(client, positions)

# ── Datos de mercado ───────────────────────────────────────────────────────
df_h1 = client.get_prices(EPIC, 'HOUR',   100)
df_h4 = client.get_prices(EPIC, 'HOUR_4',  50)

if df_h1 is None or df_h4 is None:
    print("ERROR: Sin datos de mercado")
    sys.exit(1)

# H1 SCALP
scalp_cfg = StrategyConfig(**STRATEGY_PRESETS['SCALP']['params'])
df_h1 = calculate_indicators(df_h1, scalp_cfg)
df_h1 = generate_signals(df_h1, scalp_cfg)

# H4 SWING (confirmacion)
swing_cfg = StrategyConfig(**STRATEGY_PRESETS['SWING']['params'])
df_h4 = calculate_indicators(df_h4, swing_cfg)
df_h4 = generate_signals(df_h4, swing_cfg)

h1_cur  = df_h1.iloc[-1]
h1_prev = df_h1.iloc[-2]
h4_last = df_h4.iloc[-1]

h4_bull = h4_last['ema_fast'] > h4_last['ema_slow'] and h4_last['ema_slow'] > h4_last['ema_long']
h4_bear = h4_last['ema_fast'] < h4_last['ema_slow'] and h4_last['ema_slow'] < h4_last['ema_long']
h4_trend = "ALCISTA" if h4_bull else ("BAJISTA" if h4_bear else "MIXTA/LATERAL")

h1_bull_ema = h1_prev['ema_fast'] > h1_prev['ema_slow'] and h1_prev['ema_slow'] > h1_prev['ema_long']
h1_bear_ema = h1_prev['ema_fast'] < h1_prev['ema_slow'] and h1_prev['ema_slow'] < h1_prev['ema_long']
h1_ema_align = "ALCISTA" if h1_bull_ema else ("BAJISTA" if h1_bear_ema else "MIXTA")

print()
print("MERCADO")
print("  Precio   : " + str(round(float(h1_cur['close']), 2)))
print("  RSI H1   : " + str(round(float(h1_prev['rsi']), 1)))
print("  ATR H1   : " + str(round(float(h1_prev['atr']), 2)))
print("  EMA H1   : " + str(round(float(h1_prev['ema_fast']), 2))
      + " / " + str(round(float(h1_prev['ema_slow']), 2))
      + " / " + str(round(float(h1_prev['ema_long']), 2))
      + "  [" + h1_ema_align + "]")
print("  Tend. H4 : " + h4_trend + " | RSI H4: " + str(round(float(h4_last['rsi']), 1)))

# ── Evaluar senyal ─────────────────────────────────────────────────────────
signal = None
if h1_prev['buy_signal']:
    signal = 'BUY'
elif h1_prev['sell_signal']:
    signal = 'SELL'

print()
if signal is None:
    print("SENYAL: Sin senyal - esperando")
    sys.exit(0)

print("SENYAL: " + signal)

# ── Salvaguarda 0: viernes cierre de semana ────────────────────────────────
if friday_close:
    print("  BLOQUEADA: Viernes despues de las 17:00 — cierre de semana")
    print("  -> No se abren trades hasta el lunes.")
    sys.exit(0)

# ── Salvaguarda 1: conflicto H4 ────────────────────────────────────────────
if (signal == 'BUY' and h4_bear) or (signal == 'SELL' and h4_bull):
    print("  BLOQUEADA: H4 " + h4_trend + " contradice " + signal)
    print("  -> No se abre. Esperar alineacion H4.")
    sys.exit(0)

# ── Salvaguarda 2: ya existe posicion en la misma direccion ───────────────
gold_positions = [p for p in positions if str(p.get('epic', '')).upper() == EPIC]
same_dir = [p for p in gold_positions if p.get('direction', '') == signal]
if same_dir:
    print("  BLOQUEADA: Ya existe posicion " + signal + " en " + EPIC)
    print("  -> No se duplica. Vigilando la actual.")
    sys.exit(0)

# ── Salvaguarda 3: max riesgo abierto (5% equity) ─────────────────────────
max_risk_usd   = equity * (MAX_RISK_OPEN / 100)
riesgo_abierto = len(positions) * (equity * RISK_PCT / 100)
if riesgo_abierto >= max_risk_usd:
    print("  BLOQUEADA: Riesgo abierto $" + str(round(riesgo_abierto, 2))
          + " >= max $" + str(round(max_risk_usd, 2)))
    sys.exit(0)

# ── Salvaguarda 4: drawdown abierto maximo ────────────────────────────────
if pnl_open < -(equity * MAX_DD_PCT / 100):
    print("  BLOQUEADA: Drawdown abierto $" + str(round(pnl_open, 2))
          + " supera limite -" + str(MAX_DD_PCT) + "%")
    sys.exit(0)

# ── Salvaguarda 5: stop diario (-5% equity) ───────────────────────────────
today_str = now_utc.strftime('%Y-%m-%d')
pnl_dia   = 0.0
if os.path.exists(LOG_PATH):
    with open(LOG_PATH, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            if row.get('date') == today_str:
                try:
                    pnl_dia += float(row.get('pnl_usd') or 0)
                except Exception:
                    pass

max_loss_dia = equity * (MAX_DD_DAY_PCT / 100)
print("  P&L hoy   : $" + str(round(pnl_dia, 2))
      + " | Limite diario: -$" + str(round(max_loss_dia, 2)))

if pnl_dia <= -max_loss_dia:
    print("  BLOQUEADA: Stop diario activado ($" + str(round(pnl_dia, 2)) + ")")
    print("  -> No se abre ningun trade mas hoy. Reanudar manana.")
    sys.exit(0)

# ── Salvaguarda 6: cooling-off tras SL en misma dir hoy ──────────────────
sl_hoy_misma_dir = False
if os.path.exists(LOG_PATH):
    with open(LOG_PATH, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            if (row.get('date') == today_str and
                    row.get('epic', '').upper() == EPIC and
                    row.get('direction', '') == signal and
                    row.get('result', '').upper() == 'SL'):
                sl_hoy_misma_dir = True

if sl_hoy_misma_dir:
    rsi_val = float(h1_prev['rsi'])
    rsi_ok  = 35 <= rsi_val <= 65
    ema_ok  = (h1_bull_ema if signal == 'BUY' else h1_bear_ema)
    if not (rsi_ok and ema_ok):
        print("  BLOQUEADA: Cooling-off — SL previo hoy en " + signal)
        print("  RSI H1=" + str(round(rsi_val, 1))
              + " (necesita 35-65) | EMA=" + h1_ema_align
              + " (necesita ALCISTA para BUY / BAJISTA para SELL)")
        print("  -> Esperar condiciones neutrales antes de re-entrar.")
        sys.exit(0)
    else:
        print("  Cooling-off OK: RSI=" + str(round(rsi_val, 1))
              + " y EMA=" + h1_ema_align + " — re-entrada permitida")

# ── Calcular niveles ───────────────────────────────────────────────────────
current_price = float(h1_cur['close'])
sl_dist = float(h1_prev['sl_distance'])
tp_dist = float(h1_prev['tp_distance'])

if signal == 'BUY':
    sl = round(current_price - sl_dist, 2)
    tp = round(current_price + tp_dist, 2)
else:
    sl = round(current_price + sl_dist, 2)
    tp = round(current_price - tp_dist, 2)

size = get_position_size(equity, sl_dist, RISK_PCT)

print("  Entry : " + str(current_price))
print("  SL    : " + str(sl) + " (dist: " + str(round(sl_dist, 2)) + " pts)")
print("  TP    : " + str(tp) + " (dist: " + str(round(tp_dist, 2)) + " pts)")
print("  R:R   : 1:" + str(round(tp_dist / sl_dist, 2)))
print("  Size  : " + str(round(size, 4)) + " | Riesgo: $" + str(round(sl_dist * size, 2)))
print("  H4    : " + h4_trend + " -> OK")

# ── Abrir posicion ─────────────────────────────────────────────────────────
print()
print("Abriendo posicion automaticamente...")
deal_id      = None
final_size   = None
for attempt_size in [round(size, 2), 0.05, 0.01]:
    deal_id = client.open_position(
        epic=EPIC, direction=signal, size=attempt_size,
        stop_loss=sl, take_profit=tp
    )
    if deal_id:
        final_size = attempt_size
        print("ABIERTA OK | Deal: " + deal_id + " | Size: " + str(attempt_size)
              + " | Riesgo real: $" + str(round(sl_dist * attempt_size, 2)))
        break
    print("  Size " + str(attempt_size) + " rechazado, probando menor...")

if deal_id:
    with open(LOG_PATH, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            now_utc.strftime('%Y-%m-%d'),
            EPIC, signal,
            round(current_price, 2), sl, tp,
            final_size, '', 'OPEN',
            round(equity, 2),
            'DealID:' + deal_id + ' | Abierto automaticamente'
        ])
else:
    print("ERROR: No se pudo abrir la posicion.")

print()
print("=" * 55)
