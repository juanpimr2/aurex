# -*- coding: utf-8 -*-
import os, sys
os.environ.setdefault('CAPITAL_MODE', 'REAL')
sys.path.insert(0, '.')

from capital_client import CapitalClient
from backtester import BacktestConfig, run_backtest
from strategy import StrategyConfig, STRATEGY_PRESETS

client = CapitalClient()
client.login()

configs = [
    ('SWING_DAY',    'DAY',    'SWING',              500, 1.5),
    ('SWING_CONS',   'DAY',    'SWING_CONSERVATIVE', 500, 1.0),
    ('SCALP_H4',     'HOUR_4', 'SCALP',              500, 1.0),
    ('SCALP_H1',     'HOUR',   'SCALP',              500, 1.0),
]

print("=" * 70)
print("BACKTEST MULTI-ESTRATEGIA | Capital inicial: $250")
print("=" * 70)

for name, tf, preset, candles, risk in configs:
    df = client.get_prices('GOLD', tf, candles)
    if df is None:
        print(name + ': SIN DATOS')
        continue

    params = STRATEGY_PRESETS[preset]['params'].copy()
    params['risk_pct'] = risk
    bt = BacktestConfig(
        epic='GOLD', timeframe=tf, initial_capital=250.0,
        risk_pct=risk, spread_points=0.5, max_candles=candles,
        strategy=StrategyConfig(**params)
    )
    r = run_backtest(df, bt)
    s = r.stats

    if 'error' in s:
        print(name + ': ' + s['error'])
        continue

    first = df['timestamp'].iloc[0].strftime('%Y-%m-%d')
    last  = df['timestamp'].iloc[-1].strftime('%Y-%m-%d')
    months = max((df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]).days / 30.0, 0.01)

    print()
    print("--- " + name + " | " + first + " a " + last + " ---")
    print("  Trades totales : " + str(s['total_trades']) + "  (" + str(round(s['total_trades']/months, 1)) + "/mes)")
    print("  Win Rate       : " + str(s['win_rate_pct']) + "%")
    print("  Profit Factor  : " + str(s['profit_factor']))
    print("  Expectancy/tr  : $" + str(s['expectancy_per_trade']))
    print("  Return total   : " + str(s['total_return_pct']) + "%  (" + str(round(s['total_return_pct']/months, 1)) + "%/mes)")
    print("  Capital final  : $" + str(s['final_equity']) + "  (inicio: $250)")
    print("  Max Drawdown   : " + str(s['max_drawdown_pct']) + "%  ($" + str(s['max_drawdown_money']) + ")")
    print("  Avg WIN        : $" + str(s['avg_win_money']))
    print("  Avg LOSS       : $" + str(s['avg_loss_money']))
    print("  Racha WIN/LOSS : " + str(s['max_win_streak']) + " / " + str(s['max_loss_streak']))
    print("  Spread pagado  : $" + str(s['total_spread_cost']))
    verdict_clean = s['verdict'].encode('ascii', 'replace').decode('ascii')
    print("  >> " + verdict_clean)

print()
print("=" * 70)
print("NOTA: Position sizing usa formula ATR-based (sin cap de margen).")
print("Con cuenta $250 y margen 100%, tamano real = min(size_calculado, 0.05)")
print("Esto reduce P&L proporcional pero mantiene win rate y profit factor.")
print("=" * 70)
