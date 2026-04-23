# -*- coding: utf-8 -*-
import os, sys
os.environ.setdefault('CAPITAL_MODE', 'REAL')
sys.path.insert(0, '.')
from capital_client import CapitalClient
from backtester import BacktestConfig, run_backtest
from strategy import StrategyConfig, STRATEGY_PRESETS

client = CapitalClient()
client.login()
df = client.get_prices('GOLD', 'HOUR', 500)

base = STRATEGY_PRESETS['SCALP']['params'].copy()
base['atr_sl_mult'] = 0.8
base['atr_tp_mult'] = 2.0
base['risk_pct'] = 1.0

print("=" * 65)
print("TEST VOL_MULT | SCALP H1 GOLD | SL 0.8x / TP 2.0x")
print("=" * 65)
months = max((df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]).days / 30.0, 0.01)

for vol_m in [1.2, 1.0, 0.8, 0.5, 0.0]:
    params = base.copy()
    params['vol_mult'] = vol_m
    bt = BacktestConfig(
        epic='GOLD', timeframe='HOUR', initial_capital=250.0,
        risk_pct=1.0, spread_points=0.5, max_candles=500,
        strategy=StrategyConfig(**params)
    )
    r = run_backtest(df, bt)
    s = r.stats
    if 'error' in s:
        print("vol_mult=" + str(vol_m) + ": sin trades")
        continue
    ret_mo = round(s['total_return_pct'] / months, 2)
    verdict = s['verdict'].encode('ascii','replace').decode('ascii')
    print("vol_mult=" + str(vol_m)
          + " | trades=" + str(s['total_trades']) + " (" + str(round(s['total_trades']/months,1)) + "/mes)"
          + " | WR=" + str(s['win_rate_pct']) + "%"
          + " | PF=" + str(s['profit_factor'])
          + " | ret=" + str(ret_mo) + "%/mes"
          + " | MaxDD=" + str(s['max_drawdown_pct']) + "%"
          + " | exp=$" + str(s['expectancy_per_trade']))
print("=" * 65)
