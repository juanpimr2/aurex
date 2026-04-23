# -*- coding: utf-8 -*-
"""
Test de diferentes configuraciones SL/TP para SCALP H1
Objetivo: encontrar el mejor R:R con expectancy positiva
"""
import os, sys
os.environ.setdefault('CAPITAL_MODE', 'REAL')
sys.path.insert(0, '.')

from capital_client import CapitalClient
from backtester import BacktestConfig, run_backtest
from strategy import StrategyConfig, STRATEGY_PRESETS

client = CapitalClient()
client.login()

df_h1 = client.get_prices('GOLD', 'HOUR', 500)
if df_h1 is None:
    print("Sin datos")
    sys.exit(1)

# Parametros base SCALP (EMA 5/13/21, RSI 10, bounds 30/70)
base = STRATEGY_PRESETS['SCALP']['params'].copy()

# Combinaciones SL/TP a testear
# Scalpers profesionales: SL ajustado, TP amplio (R:R >= 1:2)
combos = [
    # (nombre,          sl_mult, tp_mult)
    ("Actual (1.5/2.0)",  1.5,  2.0),   # R:R 1:1.33 - actual
    ("Ajust (1.0/2.0)",   1.0,  2.0),   # R:R 1:2.0
    ("Ajust (1.0/2.5)",   1.0,  2.5),   # R:R 1:2.5
    ("Ajust (0.8/2.0)",   0.8,  2.0),   # R:R 1:2.5
    ("Optim (1.0/3.0)",   1.0,  3.0),   # R:R 1:3.0
    ("Tight (0.5/1.5)",   0.5,  1.5),   # R:R 1:3.0 muy ajustado
    ("Wide  (2.0/4.0)",   2.0,  4.0),   # R:R 1:2.0 amplio
]

print("=" * 75)
print("TEST R:R - SCALP H1 GOLD | Capital: $250 | ~13 meses de datos")
print("=" * 75)
print("{:<22} {:>5} {:>7} {:>6} {:>8} {:>8} {:>7} {:>7}".format(
    "Config", "Trades", "WinRate", "PF", "Ret/mes", "MaxDD%", "AvgWIN", "AvgLOSS"))
print("-" * 75)

best = None
best_score = -999

for name, sl_m, tp_m in combos:
    params = base.copy()
    params['atr_sl_mult'] = sl_m
    params['atr_tp_mult'] = tp_m
    params['risk_pct'] = 1.0

    bt = BacktestConfig(
        epic='GOLD', timeframe='HOUR', initial_capital=250.0,
        risk_pct=1.0, spread_points=0.5, max_candles=500,
        strategy=StrategyConfig(**params)
    )
    r = run_backtest(df_h1, bt)
    s = r.stats

    if 'error' in s:
        print(name + ": sin trades")
        continue

    months = max((df_h1['timestamp'].iloc[-1] - df_h1['timestamp'].iloc[0]).days / 30.0, 0.01)
    ret_mo = round(s['total_return_pct'] / months, 2)
    rr = round(tp_m / sl_m, 2)

    # Score = profit_factor * win_rate / max_drawdown
    score = s['profit_factor'] * (s['win_rate_pct']/100) / max(s['max_drawdown_pct'], 1)
    if score > best_score:
        best_score = score
        best = (name, sl_m, tp_m, s, rr, ret_mo)

    verdict_short = "OK" if s['profit_factor'] >= 1.5 else ("MRG" if s['profit_factor'] >= 1.2 else "NO")

    print("{:<22} {:>5} {:>6}% {:>6} {:>7}%/m {:>7}% {:>7} {:>7}  R:R 1:{} [{}]".format(
        name,
        s['total_trades'],
        s['win_rate_pct'],
        s['profit_factor'],
        ret_mo,
        s['max_drawdown_pct'],
        "$"+str(s['avg_win_money']),
        "$"+str(s['avg_loss_money']),
        rr,
        verdict_short
    ))

print()
if best:
    name, sl_m, tp_m, s, rr, ret_mo = best
    months = max((df_h1['timestamp'].iloc[-1] - df_h1['timestamp'].iloc[0]).days / 30.0, 0.01)
    print(">> MEJOR CONFIG: " + name)
    print("   SL=" + str(sl_m) + "x ATR | TP=" + str(tp_m) + "x ATR | R:R 1:" + str(rr))
    print("   Win Rate: " + str(s['win_rate_pct']) + "% | PF: " + str(s['profit_factor']))
    print("   Return/mes: " + str(ret_mo) + "% | MaxDD: " + str(s['max_drawdown_pct']) + "%")
    print("   Expectancy/trade: $" + str(s['expectancy_per_trade']))
    print("   Meses para doblar cuenta: " + str(round(70/ret_mo,1)) if ret_mo > 0 else "   No rentable")
