# -*- coding: utf-8 -*-
"""
Walk-forward SWING DAY: ACTUAL (TP 2.5x) vs PROPUESTA (TP 3.5x)
==============================================================
SOLO LECTURA / ANALISIS. No toca broker, ordenes ni el preset en produccion.

Validacion de robustez: divide el histgrico DAY en tramos cronologicos
consecutivos (folds) y compara ambas configuraciones en CADA tramo por
separado. Si la propuesta gana solo en el total pero pierde en varios
tramos -> es sobreajuste y NO se debe aplicar. Si gana en la mayoria de
tramos -> es robusta.

SL fijo en 2.0x ATR en ambas (el backtest previo mostro que ampliar SL
empeora). Riesgo 5% (produccion). Solo cambia el TP.

Uso: python bt_wf_swing.py
"""
import os, sys
os.environ.setdefault('CAPITAL_MODE', 'REAL')
sys.path.insert(0, '.')

from capital_client import CapitalClient
from backtester import BacktestConfig, run_backtest
from strategy import StrategyConfig, STRATEGY_PRESETS

N_FOLDS = 4

client = CapitalClient()
client.login()

df = client.get_prices('GOLD', 'DAY', 700)
if df is None or len(df) < 80:
    print("Sin datos suficientes DAY")
    sys.exit(1)

df = df.reset_index(drop=True)
base = STRATEGY_PRESETS['SWING']['params'].copy()


def run_cfg(sub_df, sl_m, tp_m):
    params = base.copy()
    params['atr_sl_mult'] = sl_m
    params['atr_tp_mult'] = tp_m
    params['risk_pct'] = 5.0
    bt = BacktestConfig(
        epic='GOLD', timeframe='DAY', initial_capital=250.0,
        risk_pct=5.0, spread_points=0.5, max_candles=700,
        strategy=StrategyConfig(**params)
    )
    r = run_backtest(sub_df, bt)
    return r.stats


n = len(df)
fold_size = n // N_FOLDS

print("=" * 88)
print("WALK-FORWARD SWING DAY GOLD | " + str(n) + " velas | " + str(N_FOLDS)
      + " tramos | SL 2.0x fijo | riesgo 5%")
print("ACTUAL = TP 2.5x (R:R 1.25)  vs  PROPUESTA = TP 3.5x (R:R 1.75)")
print("=" * 88)

wins_prop = 0
valid_folds = 0

for i in range(N_FOLDS):
    a = i * fold_size
    b = (i + 1) * fold_size if i < N_FOLDS - 1 else n
    sub = df.iloc[a:b].reset_index(drop=True)
    d0 = str(sub['timestamp'].iloc[0])[:10]
    d1 = str(sub['timestamp'].iloc[-1])[:10]

    s_act = run_cfg(sub, 2.0, 2.5)
    s_pro = run_cfg(sub, 2.0, 3.5)

    print()
    print("TRAMO " + str(i + 1) + "  (" + d0 + " -> " + d1 + " | " + str(len(sub)) + " velas)")

    def line(tag, s):
        if 'error' in s or s.get('total_trades', 0) == 0:
            print("  {:<10} sin trades".format(tag))
            return None
        print("  {:<10} trades={:>2} | WR={:>5}% | PF={:>5} | Ret={:>7}% | DD={:>5}%".format(
            tag, s['total_trades'], s['win_rate_pct'], s['profit_factor'],
            s['total_return_pct'], s['max_drawdown_pct']))
        return s

    ra = line("ACTUAL", s_act)
    rp = line("PROPUESTA", s_pro)

    if ra and rp:
        valid_folds += 1
        # Comparacion por retorno total del tramo (out-of-sample)
        if rp['total_return_pct'] > ra['total_return_pct']:
            wins_prop += 1
            print("  -> PROPUESTA gana este tramo (+"
                  + str(round(rp['total_return_pct'] - ra['total_return_pct'], 2)) + " pts)")
        else:
            print("  -> ACTUAL gana este tramo (+"
                  + str(round(ra['total_return_pct'] - rp['total_return_pct'], 2)) + " pts)")

print()
print("=" * 88)
print("RESUMEN WALK-FORWARD")
print("  Tramos validos (ambas con trades): " + str(valid_folds) + "/" + str(N_FOLDS))
print("  Tramos donde PROPUESTA (TP 3.5) supera a ACTUAL: " + str(wins_prop)
      + "/" + str(valid_folds))
if valid_folds > 0:
    if wins_prop == valid_folds:
        print("  VEREDICTO: ROBUSTA — gana en TODOS los tramos. Cambio justificado.")
    elif wins_prop >= (valid_folds + 1) // 2 + (1 if valid_folds > 2 else 0):
        print("  VEREDICTO: MAYORITARIA — gana en la mayoria. Cambio razonable con cautela.")
    else:
        print("  VEREDICTO: NO ROBUSTA — no gana consistentemente. NO aplicar (posible sobreajuste).")
print("=" * 88)
print("NOTA: muestra pequena por tramo. Interpretar como indicio, no prueba.")
print("Decision de cambio en produccion requiere aprobacion explicita.")
