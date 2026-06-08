# -*- coding: utf-8 -*-
"""
Reporte Diario de Sesion - Aurex
=================================
Ejecutar al cierre de sesion (23:00 hora local / 21:00 UTC).
Analiza trades reales + senales M15 observadas del dia.
Genera informe estructurado para revision humana y mejora continua.
"""
import os, sys
os.environ.setdefault('CAPITAL_MODE', 'REAL')
sys.path.insert(0, '.')

import csv
from datetime import datetime, timezone, date

TRADE_LOG  = os.path.join(os.path.dirname(__file__), 'trade_log.csv')
M15_LOG    = os.path.join(os.path.dirname(__file__), 'm15_signal_log.csv')
SWING_LOG  = os.path.join(os.path.dirname(__file__), 'swing_signal_log.csv')
REPORT_DIR = os.path.join(os.path.dirname(__file__), 'daily_reports')
os.makedirs(REPORT_DIR, exist_ok=True)

today     = date.today().isoformat()
now_utc   = datetime.now(timezone.utc)
sep       = "=" * 65

# ── Leer trades reales del dia ─────────────────────────────────────
trades_hoy = []
balance_inicio = None
balance_fin    = None

with open(TRADE_LOG, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    all_trades = list(reader)

for t in all_trades:
    if t['date'] == today:
        trades_hoy.append(t)

# Balance inicio = balance_after del ultimo trade ANTES de hoy
for t in all_trades:
    if t['date'] < today and t.get('balance_after'):
        try:
            balance_inicio = float(t['balance_after'])
        except:
            pass

if trades_hoy:
    try:
        balance_fin = float(trades_hoy[-1]['balance_after'])
    except:
        pass
    if balance_inicio is None:
        # Si no hay trades previos, buscar primer trade del dia
        try:
            balance_inicio = float(trades_hoy[0]['balance_after']) - float(trades_hoy[0]['pnl_usd'] or 0)
        except:
            balance_inicio = 250.0

# ── Leer senales M15 del dia ───────────────────────────────────────
m15_hoy = []
with open(M15_LOG, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row['datetime_utc'].startswith(today):
            m15_hoy.append(row)

# ── Leer senales SWING del dia ─────────────────────────────────────
swing_hoy = []
if os.path.exists(SWING_LOG):
    with open(SWING_LOG, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['datetime_utc'].startswith(today):
                swing_hoy.append(row)

# Acumular: todos los SWING historicos para estadisticas globales
swing_all = []
if os.path.exists(SWING_LOG):
    with open(SWING_LOG, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        swing_all = list(reader)

# ── Calcular metricas de trades reales ────────────────────────────
pnl_total   = 0.0
wins        = 0
losses      = 0
sl_hits     = 0
tp_hits     = 0
open_trades = 0

for t in trades_hoy:
    result = t.get('result', '').upper()
    pnl    = float(t.get('pnl_usd') or 0)
    pnl_total += pnl
    if result == 'TP':
        wins    += 1
        tp_hits += 1
    elif result == 'SL':
        losses  += 1
        sl_hits += 1
    elif result == 'OPEN':
        open_trades += 1

total_cerrados = wins + losses
wr = round(wins / total_cerrados * 100, 1) if total_cerrados > 0 else 0

# ── Calcular metricas M15 observacion ────────────────────────────
m15_buys  = [s for s in m15_hoy if s['direction'] == 'BUY']
m15_sells = [s for s in m15_hoy if s['direction'] == 'SELL']

# ── Detectar patrones del dia ─────────────────────────────────────
reentrada_rapida = False
for i in range(1, len(trades_hoy)):
    t_prev = trades_hoy[i-1]
    t_curr = trades_hoy[i]
    if (t_prev.get('result','').upper() == 'SL' and
        t_curr.get('direction','') == t_prev.get('direction','') and
        t_curr.get('epic','') == t_prev.get('epic','')):
        reentrada_rapida = True

m15_vs_h1_conflict = sum(
    1 for s in m15_hoy
    if s['direction'] == 'SELL' and
    any(t['direction'] == 'BUY' and t['date'] == today for t in trades_hoy)
)

# ── Imprimir reporte ───────────────────────────────────────────────
print(sep)
print("AUREX | REPORTE DIARIO DE SESION | " + today)
print("Generado: " + now_utc.strftime('%H:%M UTC'))
print(sep)

# -- Resumen P&L
print()
print("RESULTADO DEL DIA")
print("  Trades ejecutados : " + str(len(trades_hoy)))
if trades_hoy:
    print("  Cerrados          : " + str(total_cerrados) + " (TP: " + str(tp_hits) + " | SL: " + str(sl_hits) + ")")
    print("  Abiertos al cierre: " + str(open_trades))
    print("  Win Rate          : " + str(wr) + "%")
    print("  P&L del dia       : $" + str(round(pnl_total, 2)))
    if balance_inicio and balance_fin:
        print("  Balance inicio    : $" + str(round(balance_inicio, 2)))
        print("  Balance cierre    : $" + str(round(balance_fin, 2)))
        cambio_pct = round((balance_fin - balance_inicio) / balance_inicio * 100, 2)
        print("  Variacion         : " + str(cambio_pct) + "%")
else:
    print("  Sin trades ejecutados hoy.")

# -- Detalle trades
if trades_hoy:
    print()
    print("DETALLE TRADES")
    for i, t in enumerate(trades_hoy, 1):
        pnl_str = ("$" + str(t.get('pnl_usd','?'))) if t.get('pnl_usd') else "abierto"
        print("  " + str(i) + ". " + t['direction'] + " entry=" + str(t['entry'])
              + " | result=" + t.get('result','?')
              + " | P&L=" + pnl_str)
        if t.get('notes'):
            print("     " + t['notes'])

# -- Trades M15 reales del dia
m15_real = [s for s in m15_hoy if 'REAL' in str(s.get('notas', ''))]
m15_obs  = [s for s in m15_hoy if s not in m15_real]

print()
print("TRADES M15 REALES")
print("  Trades hoy        : " + str(len(m15_real)))
print("  BUY               : " + str(len([s for s in m15_real if s['direction'] == 'BUY'])))
print("  SELL              : " + str(len([s for s in m15_real if s['direction'] == 'SELL'])))
if m15_real:
    m15_abiertos = [s for s in m15_real if 'OPEN' in str(s.get('resultado', ''))]
    m15_error    = [s for s in m15_real if 'ERROR' in str(s.get('resultado', ''))]
    print("  Abiertos          : " + str(len(m15_abiertos)))
    if m15_error:
        print("  Errores apertura  : " + str(len(m15_error)))

if m15_obs:
    print()
    print("OBSERVACION M15 (sin dinero)")
    print("  Senales           : " + str(len(m15_obs)))
if m15_vs_h1_conflict > 0:
    print("  Conflictos M15 vs H1 BUY: " + str(m15_vs_h1_conflict) + " senales SELL durante trade BUY activo")

# -- Trades SWING del dia
swing_real = [s for s in swing_hoy if 'real' in str(s.get('notas', '')).lower()]
swing_obs  = [s for s in swing_hoy if s not in swing_real]
swing_open_hoy    = [s for s in swing_real if 'PENDIENTE' in str(s.get('resultado', ''))]
swing_cerrado_hoy = [s for s in swing_real if s not in swing_open_hoy]

print()
print("TRADES SWING DAY")
print("  Trades hoy        : " + str(len(swing_real)))
print("  BUY               : " + str(len([s for s in swing_real if s['direction'] == 'BUY'])))
print("  SELL              : " + str(len([s for s in swing_real if s['direction'] == 'SELL'])))
if swing_real:
    print("  Abiertos (PEND.)  : " + str(len(swing_open_hoy)))
    print("  Cerrados hoy      : " + str(len(swing_cerrado_hoy)))
    pnl_swing_hoy = sum(float(s.get('pnl_teorico_usd') or 0) for s in swing_cerrado_hoy)
    if swing_cerrado_hoy:
        print("  P&L SWING cerrados: $" + str(round(pnl_swing_hoy, 2)))
    for i, s in enumerate(swing_real, 1):
        rr_str = "RR 1:" + str(s.get('rr','?'))
        pnl_str = ("$" + str(s.get('pnl_teorico_usd','?'))) if s.get('pnl_teorico_usd') else "abierto"
        print("  " + str(i) + ". " + s['direction']
              + " entry=" + str(s.get('entry_price','?'))
              + " | " + rr_str
              + " | resultado=" + str(s.get('resultado','?'))
              + " | P&L=" + pnl_str)
if swing_obs:
    print("  Observacion SWING : " + str(len(swing_obs)) + " senales (sin dinero real)")

# -- Estadisticas SWING acumuladas
if swing_all:
    swing_all_real   = [s for s in swing_all if 'real' in str(s.get('notas', '')).lower()]
    swing_all_cerr   = [s for s in swing_all_real if 'PENDIENTE' not in str(s.get('resultado', ''))]
    swing_all_tp     = [s for s in swing_all_cerr if 'TP' in str(s.get('resultado', '')).upper()]
    swing_all_sl     = [s for s in swing_all_cerr if 'SL' in str(s.get('resultado', '')).upper()]
    swing_pnl_acum   = sum(float(s.get('pnl_teorico_usd') or 0) for s in swing_all_cerr)
    swing_wr = round(len(swing_all_tp) / len(swing_all_cerr) * 100, 1) if swing_all_cerr else 0
    print()
    print("SWING ACUMULADO")
    print("  Trades totales    : " + str(len(swing_all_real)) + " (" + str(len(swing_all_cerr)) + " cerrados)")
    print("  TP / SL           : " + str(len(swing_all_tp)) + " / " + str(len(swing_all_sl)))
    print("  Win Rate SWING    : " + str(swing_wr) + "%")
    print("  P&L SWING acum.   : $" + str(round(swing_pnl_acum, 2)))

# -- Analisis de fallos
print()
print("ANALISIS DE FALLOS / PATRONES DETECTADOS")

fallos = []
mejoras = []

if sl_hits >= 2:
    fallos.append("Multiples SL en el mismo dia (" + str(sl_hits) + ")")
    mejoras.append("Considerar pausa tras 2 SL consecutivos en la misma sesion")

if reentrada_rapida:
    fallos.append("Re-entrada inmediata tras SL en la misma direccion")
    mejoras.append("Implementar cooling-off: esperar RSI < 40 o > 60 y EMAs alineadas tras SL")

if m15_vs_h1_conflict >= 3:
    fallos.append("M15 bajista durante trade H1 BUY activo (" + str(m15_vs_h1_conflict) + " senales SELL M15)")
    mejoras.append("Usar M15 como filtro adicional: si M15 bajista, no abrir H1 BUY")

if pnl_total < -5:
    fallos.append("Perdida diaria supera $5 (limite recomendado)")
    mejoras.append("Activar stop diario: pausar trading si P&L dia < -$5")

if not fallos:
    print("  Sin fallos criticos detectados hoy.")
else:
    for f in fallos:
        print("  [!] " + f)

# -- Mejoras propuestas
if mejoras:
    print()
    print("MEJORAS PROPUESTAS PARA MANANA")
    for i, m in enumerate(mejoras, 1):
        print("  " + str(i) + ". " + m)

# -- Comparacion vs backtest
print()
print("CONTEXTO HISTORICO")
print("  Backtest H1 esperado : ~12-14%/mes | ~$30-35/mes con $250")
print("  Objetivo realista/dia: $1.0 - $1.5 promedio (algunos dias positivo, otros negativo)")
print("  Trades totales acum  : " + str(len(all_trades)))

tp_total  = sum(1 for t in all_trades if t.get('result','').upper() == 'TP')
sl_total  = sum(1 for t in all_trades if t.get('result','').upper() == 'SL')
pnl_acum  = sum(float(t.get('pnl_usd') or 0) for t in all_trades)
cerr_tot  = tp_total + sl_total
wr_total  = round(tp_total / cerr_tot * 100, 1) if cerr_tot > 0 else 0

print("  TP acumulados        : " + str(tp_total) + " | SL: " + str(sl_total))
print("  Win Rate total       : " + str(wr_total) + "%")
print("  P&L acumulado        : $" + str(round(pnl_acum, 2)))

# -- Guardar reporte
report_path = os.path.join(REPORT_DIR, 'report_' + today + '.txt')
print()
print(sep)
print("Reporte guardado en: daily_reports/report_" + today + ".txt")
print(sep)

# Actualizar registro historico automaticamente
try:
    import importlib.util, subprocess, sys
    subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), 'update_docs.py')],
                   capture_output=True, timeout=10)
except Exception:
    pass

# Escribir a archivo
import io
import contextlib

output = io.StringIO()
# El reporte ya se mostro por pantalla — guardamos un resumen estructurado
with open(report_path, 'w', encoding='utf-8') as rf:
    rf.write("AUREX DAILY REPORT | " + today + "\n")
    rf.write("Generado: " + now_utc.strftime('%Y-%m-%d %H:%M UTC') + "\n\n")
    rf.write("P&L_DIA=" + str(round(pnl_total, 2)) + "\n")
    rf.write("TRADES=" + str(len(trades_hoy)) + "\n")
    rf.write("TP=" + str(tp_hits) + "\n")
    rf.write("SL=" + str(sl_hits) + "\n")
    rf.write("WR_DIA=" + str(wr) + "%\n")
    if balance_inicio and balance_fin:
        rf.write("BALANCE_INICIO=" + str(round(balance_inicio, 2)) + "\n")
        rf.write("BALANCE_FIN=" + str(round(balance_fin, 2)) + "\n")
    rf.write("M15_SENALES=" + str(len(m15_hoy)) + "\n")
    rf.write("M15_BUY=" + str(len(m15_buys)) + "\n")
    rf.write("M15_SELL=" + str(len(m15_sells)) + "\n")
    rf.write("SWING_TRADES_HOY=" + str(len(swing_real)) + "\n")
    rf.write("SWING_ABIERTOS=" + str(len(swing_open_hoy)) + "\n")
    rf.write("\nFALLOS:\n")
    for f in fallos:
        rf.write("  - " + f + "\n")
    rf.write("\nMEJORAS_PROPUESTAS:\n")
    for m in mejoras:
        rf.write("  - " + m + "\n")
    rf.write("\nP&L_ACUMULADO=" + str(round(pnl_acum, 2)) + "\n")
    rf.write("WR_TOTAL=" + str(wr_total) + "%\n")
