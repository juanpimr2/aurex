# -*- coding: utf-8 -*-
import os, sys
os.environ.setdefault('CAPITAL_MODE', 'REAL')
sys.path.insert(0, '.')

from capital_client import CapitalClient
from strategy import StrategyConfig, STRATEGY_PRESETS, calculate_indicators, generate_signals, get_position_size

client = CapitalClient()
if not client.login():
    print("ERROR: Login fallido")
    sys.exit(1)

bal = client.get_balance()
equity = bal['balance'] if bal else 250.0

# Obtener precio actual y calcular niveles frescos
df_h1 = client.get_prices('GOLD', 'HOUR', 100)
if df_h1 is None:
    print("ERROR: Sin datos H1")
    sys.exit(1)

scalp_params = STRATEGY_PRESETS['SCALP']['params'].copy()
scalp_cfg = StrategyConfig(**scalp_params)
df_h1 = calculate_indicators(df_h1, scalp_cfg)
df_h1 = generate_signals(df_h1, scalp_cfg)

h1_prev = df_h1.iloc[-2]  # ultima vela completa
current_price = float(df_h1.iloc[-1]['close'])

direction = 'SELL'
sl_dist = float(h1_prev['sl_distance'])
tp_dist = float(h1_prev['tp_distance'])

# SL y TP desde precio actual de mercado
sl = round(current_price + sl_dist, 2)
tp = round(current_price - tp_dist, 2)

# Tamano: intentar con formula, caer a minimo si falla por margen
calculated_size = get_position_size(equity, sl_dist, 1.0)

print("Abriendo SELL GOLD...")
print("  Precio actual : " + str(current_price))
print("  SL            : " + str(sl) + " (+" + str(round(sl_dist,2)) + " pts)")
print("  TP            : " + str(tp) + " (-" + str(round(tp_dist,2)) + " pts)")
print("  Size calculado: " + str(round(calculated_size, 4)))

# Intentar con size calculado primero, luego reducir si falla
deal_id = None
for size in [round(calculated_size, 2), 0.05, 0.01]:
    print("  Intentando size=" + str(size) + "...")
    deal_id = client.open_position(
        epic='GOLD',
        direction=direction,
        size=size,
        stop_loss=sl,
        take_profit=tp,
    )
    if deal_id:
        print()
        print("POSICION ABIERTA OK")
        print("  Deal ID   : " + deal_id)
        print("  Direction : " + direction)
        print("  Size      : " + str(size))
        print("  Entry     : ~" + str(current_price))
        print("  SL        : " + str(sl))
        print("  TP        : " + str(tp))
        print("  Riesgo    : $" + str(round(sl_dist * size, 2)))
        break
    else:
        print("  Fallido con size=" + str(size) + ", probando menor...")

if not deal_id:
    print()
    print("ERROR: No se pudo abrir la posicion en ningun tamano.")
    print("Posible causa: margen insuficiente o restriccion del broker.")
