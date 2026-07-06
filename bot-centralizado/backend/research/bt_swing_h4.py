# -*- coding: utf-8 -*-
"""
Aurex Research — Preset SWING-H4 (vehiculo intermedio)
======================================================
SOLO LECTURA. Evalua la estrategia estilo SWING (EMA 8/21/50 + RSI 14 35-65 +
BB + ATR) sobre velas H4, como vehiculo intermedio entre SWING-DAY (lento) y
M15 (fragil, suspendido 6-jul).

Datos: snapshot fijo GOLD_HOUR_4 (research/data_snapshots/), ~230 dias.
LIMITACION HONESTA: 7.5 meses de datos, un solo gran regimen (tendencia bajista
2025-26 + giro reciente). Los resultados son INDICIO, no prueba. Cualquier
activacion exigira ademas paper trading previo.

Fase 1: grid SL/TP a riesgo nominal 2%.
Fase 2: walk-forward 3 tramos de las 2 mejores configs vs referencia.

Uso: python research/bt_swing_h4.py [YYYYMMDD]
"""
import os, sys
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import pandas as pd
from backtester import BacktestConfig, run_backtest
from strategy import StrategyConfig, STRATEGY_PRESETS

SNAP_DIR = os.path.join(BASE, 'research', 'data_snapshots')
stamp = sys.argv[1] if len(sys.argv) > 1 else '20260702'
snap = os.path.join(SNAP_DIR, 'GOLD_HOUR_4_' + stamp + '.csv')
if not os.path.isfile(snap):
    print('No existe snapshot: ' + snap); sys.exit(1)

df = pd.read_csv(snap, parse_dates=['timestamp'])
months = max((df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]).days / 30.0, 0.01)

base = STRATEGY_PRESETS['SWING']['params'].copy()  # EMA 8/21/50, RSI 35-65
RISK = 2.0

combos = [
    ("SL1.5/TP3.0", 1.5, 3.0),
    ("SL1.5/TP3.5", 1.5, 3.5),
    ("SL2.0/TP2.5", 2.0, 2.5),
    ("SL2.0/TP3.0", 2.0, 3.0),
    ("SL2.0/TP3.5", 2.0, 3.5),
    ("SL2.0/TP4.0", 2.0, 4.0),
    ("SL2.5/TP3.5", 2.5, 3.5),
    ("SL2.5/TP5.0", 2.5, 5.0),
]


def run_cfg(sub, sl_m, tp_m):
    p = base.copy()
    p['atr_sl_mult'] = sl_m
    p['atr_tp_mult'] = tp_m
    p['risk_pct'] = RISK
    bt = BacktestConfig(epic='GOLD', timeframe='HOUR_4', initial_capital=250.0,
                        risk_pct=RISK, spread_points=0.5, max_candles=len(sub),
                        strategy=StrategyConfig(**p))
    return run_backtest(sub, bt).stats


print('=' * 92)
print('SWING-H4 GRID | ' + str(len(df)) + ' velas H4 (~' + str(round(months, 1))
      + ' meses) | EMA 8/21/50, RSI 35-65 | riesgo ' + str(RISK) + '%')
print('=' * 92)
print('{:<14} {:>6} {:>7} {:>6} {:>8} {:>7} {:>8} {:>9} {:>6}'.format(
    'Config', 'Trades', 'WR', 'PF', 'Ret.tot', 'MaxDD', 'AvgWIN', 'AvgLOSS', 'Exp'))
print('-' * 92)

results = []
for name, sl_m, tp_m in combos:
    s = run_cfg(df, sl_m, tp_m)
    if 'error' in s or not s.get('total_trades'):
        print('{:<14}  sin trades'.format(name)); continue
    score = s['profit_factor'] * (s['win_rate_pct'] / 100) / max(s['max_drawdown_pct'], 1)
    results.append((score, name, sl_m, tp_m, s))
    print('{:<14} {:>6} {:>6}% {:>6} {:>7}% {:>6}% {:>8} {:>9} {:>6}'.format(
        name, s['total_trades'], s['win_rate_pct'], s['profit_factor'],
        s['total_return_pct'], s['max_drawdown_pct'],
        '$' + str(s['avg_win_money']), '$' + str(s['avg_loss_money']),
        '$' + str(s['expectancy_per_trade'])))

if not results:
    print('Sin resultados.'); sys.exit(1)

results.sort(reverse=True)
top2 = results[:2]

print()
print('=' * 92)
print('WALK-FORWARD (3 tramos cronologicos) — top 2 configs')
print('=' * 92)

n = len(df)
fold = n // 3
for score, name, sl_m, tp_m, _ in top2:
    print()
    print('CONFIG ' + name + ':')
    wins = valid = 0
    for i in range(3):
        a, b = i * fold, (i + 1) * fold if i < 2 else n
        sub = df.iloc[a:b].reset_index(drop=True)
        d0, d1 = str(sub['timestamp'].iloc[0])[:10], str(sub['timestamp'].iloc[-1])[:10]
        s = run_cfg(sub, sl_m, tp_m)
        if 'error' in s or not s.get('total_trades'):
            print('  T' + str(i + 1) + ' (' + d0 + '->' + d1 + '): sin trades')
            continue
        valid += 1
        pos = s['total_return_pct'] > 0
        if pos:
            wins += 1
        print('  T{} ({}->{}): trades={:>2} | WR={:>5}% | PF={:>5} | Ret={:>7}% | DD={:>5}%  {}'.format(
            i + 1, d0, d1, s['total_trades'], s['win_rate_pct'], s['profit_factor'],
            s['total_return_pct'], s['max_drawdown_pct'], 'POSITIVO' if pos else 'NEGATIVO'))
    print('  -> Tramos positivos: ' + str(wins) + '/' + str(valid))

print()
print('NOTA: 7.5 meses de H4 = muestra corta y un solo regimen dominante.')
print('Esto es INDICIO para decidir si merece paper trading, no prueba estadistica.')
print('Activacion live requeriria: paper trading + aprobacion explicita del usuario.')
