# -*- coding: utf-8 -*-
"""
Aurex F0.4 — Baseline cuantitativo reproducible (SWING en produccion)
=====================================================================
SOLO LECTURA. Corre el backtest de la configuracion SWING EXACTA de
produccion sobre el snapshot fijo de datos (no la API), y guarda las
metricas en research/baseline_metrics.json.

Este es el punto de comparacion obligatorio: ningun cambio de estrategia
se activa si no supera este baseline de forma robusta (walk-forward, etc).

Uso: python research/baseline_swing.py [YYYYMMDD]   (default: snapshot de hoy)
"""
import os, sys, json
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import pandas as pd
from backtester import BacktestConfig, run_backtest
from strategy import StrategyConfig, STRATEGY_PRESETS

SNAP_DIR = os.path.join(BASE, 'research', 'data_snapshots')
stamp = sys.argv[1] if len(sys.argv) > 1 else datetime.now(timezone.utc).strftime('%Y%m%d')

snap_file = os.path.join(SNAP_DIR, 'GOLD_DAY_' + stamp + '.csv')
if not os.path.isfile(snap_file):
    print('No existe snapshot: ' + snap_file)
    sys.exit(1)

df = pd.read_csv(snap_file, parse_dates=['timestamp'])

# Config EXACTA de produccion (preset SWING + riesgo real 5% del monitor)
params = STRATEGY_PRESETS['SWING']['params'].copy()
params['risk_pct'] = 5.0  # override del monitor_swing.py (RISK_PCT = 5.0)

bt = BacktestConfig(
    epic='GOLD', timeframe='DAY', initial_capital=250.0,
    risk_pct=5.0, spread_points=0.5, max_candles=len(df),
    strategy=StrategyConfig(**params)
)
r = run_backtest(df, bt)
s = r.stats

months = max((df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]).days / 30.0, 0.01)

baseline = {
    'created_utc': datetime.now(timezone.utc).isoformat(),
    'snapshot': os.path.basename(snap_file),
    'data_from': str(df['timestamp'].iloc[0]),
    'data_to': str(df['timestamp'].iloc[-1]),
    'candles': len(df),
    'months': round(months, 1),
    'params': {
        'ema': '8/21/50', 'rsi': '14 (35-65)',
        'atr_sl_mult': params['atr_sl_mult'],
        'atr_tp_mult': params['atr_tp_mult'],
        'risk_pct': params['risk_pct'],
        'spread_points': 0.5,
    },
    'stats': s,
}

out = os.path.join(BASE, 'research', 'baseline_metrics.json')
with open(out, 'w', encoding='utf-8') as f:
    json.dump(baseline, f, indent=2, default=str)

print('=' * 70)
print('BASELINE SWING (produccion) | snapshot ' + stamp + ' | '
      + str(len(df)) + ' velas DAY (~' + str(round(months, 1)) + ' meses)')
print('=' * 70)
if 'error' in s:
    print('ERROR: ' + str(s['error']))
    sys.exit(1)
print('  Trades        : ' + str(s.get('total_trades')))
print('  Win rate      : ' + str(s.get('win_rate_pct')) + '%')
print('  Profit factor : ' + str(s.get('profit_factor')))
print('  Retorno total : ' + str(s.get('total_return_pct')) + '%')
print('  Ret/mes aprox : ' + str(round(s.get('total_return_pct', 0) / months, 2)) + '%')
print('  Max drawdown  : ' + str(s.get('max_drawdown_pct')) + '%')
print('  Expectancy    : $' + str(s.get('expectancy_per_trade')))
print('  Avg win/loss  : $' + str(s.get('avg_win_money')) + ' / $' + str(s.get('avg_loss_money')))
print()
print('Guardado en: ' + out)
