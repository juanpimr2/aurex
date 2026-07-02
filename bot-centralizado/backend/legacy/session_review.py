# -*- coding: utf-8 -*-
"""
Revision completa de sesion: 13-15 Abril 2026
Que paso, que capturo la estrategia, que se perdio y por que.
"""
import os, sys
os.environ.setdefault('CAPITAL_MODE', 'REAL')
sys.path.insert(0, '.')

from capital_client import CapitalClient
from strategy import StrategyConfig, STRATEGY_PRESETS, calculate_indicators, generate_signals
import pandas as pd

client = CapitalClient()
client.login()

df = client.get_prices('GOLD', 'HOUR', 100)
cfg = StrategyConfig(**STRATEGY_PRESETS['SCALP']['params'])
df = calculate_indicators(df, cfg)
df = generate_signals(df, cfg)

# Filtrar desde el 13 de abril
df['timestamp'] = pd.to_datetime(df['timestamp'])
sesion = df[df['timestamp'] >= '2026-04-13 14:00'].copy().reset_index(drop=True)

print("=" * 65)
print("REVISION DE SESION | GOLD H1 | 13-15 Abril 2026")
print("=" * 65)

precio_inicio = sesion.iloc[0]['close']
precio_actual = sesion.iloc[-1]['close']
cambio = precio_actual - precio_inicio
cambio_pct = (cambio / precio_inicio) * 100

print()
print("RESUMEN DEL ACTIVO")
print("  Precio inicio sesion (13 Apr ~16:00): $" + str(round(precio_inicio, 2)))
print("  Precio actual               (15 Apr): $" + str(round(precio_actual, 2)))
print("  Variacion: $" + str(round(cambio, 2)) + " (" + str(round(cambio_pct, 2)) + "%)")
print("  Maximo del periodo: $" + str(round(sesion['high'].max(), 2)))
print("  Minimo del periodo: $" + str(round(sesion['low'].min(), 2)))
print("  Rango total: $" + str(round(sesion['high'].max() - sesion['low'].min(), 2)))

# Senales generadas por la estrategia
buys = sesion[sesion['buy_signal'] == True]
sells = sesion[sesion['sell_signal'] == True]

print()
print("SENALES GENERADAS POR LA ESTRATEGIA (velas completas)")
print("  Senyales BUY:  " + str(len(buys)))
print("  Senyales SELL: " + str(len(sells)))

if len(sells) > 0:
    print()
    print("  SELLS:")
    for _, row in sells.iterrows():
        sl = round(row['close'] - row['sl_distance'], 2)
        tp = round(row['close'] - row['tp_distance'], 2)
        print("    " + str(row['timestamp'])[:16] + " | entry~" + str(round(row['close'],2))
              + " | SL=" + str(sl) + " | TP=" + str(tp)
              + " | RSI=" + str(round(row['rsi'],1))
              + " | Vol_ok=" + str(bool(row['volume'] > row['vol_sma'] * 1.2)))

if len(buys) > 0:
    print()
    print("  BUYS:")
    for _, row in buys.iterrows():
        sl = round(row['close'] - row['sl_distance'], 2)
        tp = round(row['close'] + row['tp_distance'], 2)
        print("    " + str(row['timestamp'])[:16] + " | entry~" + str(round(row['close'],2))
              + " | SL=" + str(sl) + " | TP=" + str(tp)
              + " | RSI=" + str(round(row['rsi'],1))
              + " | Vol_ok=" + str(bool(row['volume'] > row['vol_sma'] * 1.2)))

# Momentos de bloqueo por volumen con senyal tecnica casi valida
print()
print("OPORTUNIDADES BLOQUEADAS (RSI OK + EMA OK pero Vol insuficiente)")
bloqueadas = sesion[
    (sesion['buy_signal'] == False) &
    (sesion['sell_signal'] == False) &
    (sesion['rsi'] < 70) & (sesion['rsi'] > 30) &
    (sesion['ema_fast'] > sesion['ema_slow']) & (sesion['ema_slow'] > sesion['ema_long']) &
    (sesion['volume'] < sesion['vol_sma'] * 1.2) &
    (sesion['volume'] > sesion['vol_sma'] * 0.8)
].copy()

print("  Velas con condicion tecnica OK pero vol bajo umbral: " + str(len(bloqueadas)))
for _, row in bloqueadas.head(8).iterrows():
    vol_pct = round(row['volume'] / (row['vol_sma'] * 1.2) * 100, 0)
    print("    " + str(row['timestamp'])[:16] + " | RSI=" + str(round(row['rsi'],1))
          + " | Vol al " + str(vol_pct) + "% del umbral")

# Movimiento maximo aprovechable teorico
print()
print("MOVIMIENTO TEORICO APROVECHABLE (sin filtros, tendencia pura)")
# Precio min a max y max a min del periodo
max_price = sesion['high'].max()
min_price = sesion['low'].min()
max_time = sesion.loc[sesion['high'].idxmax(), 'timestamp']
min_time = sesion.loc[sesion['low'].idxmin(), 'timestamp']
print("  Minimo: $" + str(round(min_price,2)) + " en " + str(min_time)[:16])
print("  Maximo: $" + str(round(max_price,2)) + " en " + str(max_time)[:16])

if min_time < max_time:
    swing = max_price - min_price
    print("  Swing LONG (min->max): $" + str(round(swing,2)) + " pts")
    print("  Con 0.1 size: ganancia teorica maxima = $" + str(round(swing * 0.1, 2)))
else:
    swing = max_price - min_price
    print("  Swing SHORT (max->min): $" + str(round(swing,2)) + " pts")
    print("  Con 0.1 size: ganancia teorica maxima = $" + str(round(swing * 0.1, 2)))

print()
print("NUESTRA OPERACION REAL")
print("  Trade 1: SELL 13 Apr | Entry $4730 | SL activado | P&L: -$2.22")
print("  Balance: $250.00 -> $247.78")
print()
print("=" * 65)
