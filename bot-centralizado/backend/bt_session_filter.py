# -*- coding: utf-8 -*-
"""
Test: filtrar trades solo en sesion Londres + NY (08:00-17:00 UTC)
vs sin filtro de sesion. Hipotesis: mas volumen = mejor win rate.
"""
import os, sys
os.environ.setdefault('CAPITAL_MODE', 'REAL')
sys.path.insert(0, '.')

from capital_client import CapitalClient
from backtester import BacktestConfig, run_backtest
from strategy import StrategyConfig, STRATEGY_PRESETS
import pandas as pd

client = CapitalClient()
client.login()

df_h1 = client.get_prices('GOLD', 'HOUR', 500)
if df_h1 is None:
    print("Sin datos")
    sys.exit(1)

months = max((df_h1['timestamp'].iloc[-1] - df_h1['timestamp'].iloc[0]).days / 30.0, 0.01)
params = STRATEGY_PRESETS['SCALP']['params'].copy()
params['risk_pct'] = 1.0

def run(df, label):
    bt = BacktestConfig(
        epic='GOLD', timeframe='HOUR', initial_capital=250.0,
        risk_pct=1.0, spread_points=0.5, max_candles=500,
        strategy=StrategyConfig(**params)
    )
    r = run_backtest(df, bt)
    s = r.stats
    if 'error' in s:
        print(label + ": sin trades suficientes")
        return
    ret_mo = round(s['total_return_pct'] / months, 2)
    print(label)
    print("  Trades: " + str(s['total_trades']) + " (" + str(round(s['total_trades']/months,1)) + "/mes)")
    print("  Win Rate: " + str(s['win_rate_pct']) + "% | PF: " + str(s['profit_factor']))
    print("  Return/mes: " + str(ret_mo) + "% | MaxDD: " + str(s['max_drawdown_pct']) + "%")
    print("  Expectancy/trade: $" + str(s['expectancy_per_trade']))
    verdict = s['verdict'].encode('ascii','replace').decode('ascii')
    print("  " + verdict)
    print()

print("=" * 60)
print("TEST FILTRO DE SESION - SCALP H1 GOLD (SL 0.8x / TP 2.0x)")
print("=" * 60)
print()

# Sin filtro
run(df_h1, "SIN FILTRO (24h)")

# Solo Londres + NY: 07:00-17:00 UTC = 09:00-19:00 Madrid (verano)
df_london_ny = df_h1[df_h1['timestamp'].dt.hour.between(7, 17)].copy().reset_index(drop=True)
run(df_london_ny, "SOLO LONDON+NY (07:00-17:00 UTC)")

# Solo apertura London: 07:00-11:00 UTC (momento de mayor volatilidad)
df_open = df_h1[df_h1['timestamp'].dt.hour.between(7, 11)].copy().reset_index(drop=True)
run(df_open, "SOLO APERTURA LONDON (07:00-11:00 UTC)")

# NY session: 13:00-17:00 UTC
df_ny = df_h1[df_h1['timestamp'].dt.hour.between(13, 17)].copy().reset_index(drop=True)
run(df_ny, "SOLO SESION NY (13:00-17:00 UTC)")
