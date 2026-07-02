# -*- coding: utf-8 -*-
"""
Aurex F0.3 — Snapshot de datos historicos para backtests reproducibles
======================================================================
SOLO LECTURA. Descarga el maximo historico disponible de la API Capital.com
para GOLD en todos los timeframes usados y lo guarda como CSV fechado en
research/data_snapshots/. Genera un manifest con el rango real de cada TF.

Por que: la API devuelve una ventana movil (el historico "se mueve" cada dia).
Sin snapshot fijo, ningun backtest es reproducible ni comparable en el tiempo.

Uso: python research/snapshot_data.py   (desde backend/)
"""
import os, sys, json
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('CAPITAL_MODE', 'REAL')

from capital_client import CapitalClient

EPIC = 'GOLD'
TIMEFRAMES = ['DAY', 'HOUR_4', 'HOUR', 'MINUTE_15']
MAX_POINTS = 1000

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data_snapshots')
os.makedirs(OUT_DIR, exist_ok=True)

stamp = datetime.now(timezone.utc).strftime('%Y%m%d')

client = CapitalClient()
if not client.login():
    print('Login fallido')
    sys.exit(1)

manifest = {'created_utc': datetime.now(timezone.utc).isoformat(), 'epic': EPIC, 'timeframes': {}}

for tf in TIMEFRAMES:
    df = client.get_prices(EPIC, tf, MAX_POINTS)
    if df is None or len(df) == 0:
        print('[SNAP] ' + tf + ': SIN DATOS')
        manifest['timeframes'][tf] = {'rows': 0}
        continue
    fname = EPIC + '_' + tf + '_' + stamp + '.csv'
    fpath = os.path.join(OUT_DIR, fname)
    df.to_csv(fpath, index=False)
    d0, d1 = str(df['timestamp'].iloc[0]), str(df['timestamp'].iloc[-1])
    days = (df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]).days
    manifest['timeframes'][tf] = {
        'file': fname, 'rows': len(df),
        'from': d0, 'to': d1, 'span_days': days,
    }
    print('[SNAP] ' + tf + ': ' + str(len(df)) + ' velas | ' + d0[:10] + ' -> ' + d1[:10]
          + ' (' + str(days) + ' dias) -> ' + fname)

mpath = os.path.join(OUT_DIR, 'manifest_' + stamp + '.json')
with open(mpath, 'w', encoding='utf-8') as f:
    json.dump(manifest, f, indent=2)
print('[SNAP] Manifest: ' + mpath)
