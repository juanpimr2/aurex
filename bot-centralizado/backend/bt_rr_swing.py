# -*- coding: utf-8 -*-
"""
Test de configuraciones SL/TP para SWING DAY (GOLD)
===================================================
SOLO LECTURA / ANALISIS. No toca broker, ordenes, ni el preset en produccion.
Compara el R:R actual (SL 2.0x / TP 2.5x = 1:1.25) contra alternativas mas
amplias, con datos DAY reales de Capital.com y spread realista.

Uso: python bt_rr_swing.py
"""
import os, sys
os.environ.setdefault('CAPITAL_MODE', 'REAL')
sys.path.insert(0, '.')

from capital_client import CapitalClient
from backtester import BacktestConfig, run_backtest
from strategy import StrategyConfig, STRATEGY_PRESETS

client = CapitalClient()
client.login()

df_day = client.get_prices('GOLD', 'DAY', 700)
if df_day is None or len(df_day) < 60:
    print("Sin datos suficientes DAY")
    sys.exit(1)

base = STRATEGY_PRESETS['SWING']['params'].copy()

# Combinaciones SL/TP a testear (SWING = trades largos, SL amplio ATR-escalado)
combos = [
    # (nombre,               sl_mult, tp_mult)
    ("ACTUAL (2.0/2.5)",       2.0,  2.5),   # R:R 1:1.25 - produccion hoy
    ("R:R 1.5 (2.0/3.0)",      2.0,  3.0),   # TP mas amplio, mismo SL
    ("R:R 1.75 (2.0/3.5)",     2.0,  3.5),
    ("R:R 2.0 (2.0/4.0)",      2.0,  4.0),   # TP el doble del SL
    ("SL amplio (2.5/4.0)",    2.5,  4.0),   # R:R 1:1.6 - mas margen perdida
    ("SL amplio (2.5/5.0)",    2.5,  5.0),   # R:R 1:2.0 - margen + reward
    ("SL amplio (3.0/4.5)",    3.0,  4.5),   # R:R 1:1.5 - muy amplio
    ("SL tight (1.5/3.0)",     1.5,  3.0),   # R:R 1:2.0 - SL ajustado
]

n_days = (df_day['timestamp'].iloc[-1] - df_day['timestamp'].iloc[0]).days
months = max(n_days / 30.0, 0.01)

print("=" * 92)
print("TEST R:R - SWING DAY GOLD | Capital $250 | " + str(len(df_day))
      + " velas DAY (~" + str(round(months, 1)) + " meses) | spread real")
print("=" * 92)
print("{:<20} {:>6} {:>7} {:>6} {:>8} {:>7} {:>8} {:>9} {:>6}".format(
    "Config", "Trades", "WinRate", "PF", "Ret.tot", "MaxDD%", "AvgWIN", "AvgLOSS", "R:R"))
print("-" * 92)

best = None
best_score = -999

for name, sl_m, tp_m in combos:
    params = base.copy()
    params['atr_sl_mult'] = sl_m
    params['atr_tp_mult'] = tp_m
    params['risk_pct'] = 5.0   # riesgo SWING real en produccion

    bt = BacktestConfig(
        epic='GOLD', timeframe='DAY', initial_capital=250.0,
        risk_pct=5.0, spread_points=0.5, max_candles=700,
        strategy=StrategyConfig(**params)
    )
    r = run_backtest(df_day, bt)
    s = r.stats

    if 'error' in s or s.get('total_trades', 0) == 0:
        print("{:<20}  sin trades".format(name))
        continue

    rr = round(tp_m / sl_m, 2)
    # Score = PF * WR / MaxDD (favorece robustez, penaliza drawdown)
    score = s['profit_factor'] * (s['win_rate_pct']/100) / max(s['max_drawdown_pct'], 1)
    if score > best_score:
        best_score = score
        best = (name, sl_m, tp_m, s, rr)

    verdict = "OK" if s['profit_factor'] >= 1.5 else ("MRG" if s['profit_factor'] >= 1.2 else "NO")

    print("{:<20} {:>6} {:>6}% {:>6} {:>7}% {:>7}% {:>8} {:>9} {:>4} [{}]".format(
        name,
        s['total_trades'],
        s['win_rate_pct'],
        s['profit_factor'],
        s['total_return_pct'],
        s['max_drawdown_pct'],
        "$"+str(s['avg_win_money']),
        "$"+str(s['avg_loss_money']),
        "1:"+str(rr),
        verdict
    ))

print()
if best:
    name, sl_m, tp_m, s, rr = best
    print(">> MEJOR SCORE (robustez PF*WR/DD): " + name)
    print("   SL=" + str(sl_m) + "x ATR | TP=" + str(tp_m) + "x ATR | R:R 1:" + str(rr))
    print("   Trades: " + str(s['total_trades']) + " | WinRate: " + str(s['win_rate_pct'])
          + "% | PF: " + str(s['profit_factor']))
    print("   Return total: " + str(s['total_return_pct']) + "% | MaxDD: "
          + str(s['max_drawdown_pct']) + "%")
    print("   Expectancy/trade: $" + str(s['expectancy_per_trade']))
    print()
    print("NOTA: muestra pequena (pocos trades DAY). Interpretar con cautela,")
    print("no como verdad estadistica. Decision de cambio requiere aprobacion.")
