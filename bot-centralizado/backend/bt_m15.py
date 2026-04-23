# -*- coding: utf-8 -*-
"""
Backtest M15 - Busqueda de estrategia scalping rapida para GOLD
==============================================================
Que evaluamos:
  - 3 combinaciones de EMA (velocidades rapida/media/lenta)
  - 3 combinaciones de RSI period + bounds
  - 4 combinaciones de SL/TP (R:R distintos)
  - 2 niveles de filtro de volumen
Total: ~72 combinaciones. Mostramos solo las 10 mejores por puntuacion.

Puntuacion = PF * WR * (ret/mes) / MaxDD  (mayor es mejor)
"""
import os, sys
os.environ.setdefault('CAPITAL_MODE', 'REAL')
sys.path.insert(0, '.')

from capital_client import CapitalClient
from backtester import BacktestConfig, run_backtest
from strategy import StrategyConfig

client = CapitalClient()
client.login()

print("Descargando datos M15 (1000 velas)...")
df = client.get_prices('GOLD', 'MINUTE_15', 1000)

if df is None or len(df) < 100:
    print("ERROR: Sin datos M15")
    sys.exit(1)

months = max((df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]).days / 30.0, 0.01)
print("Periodo: " + str(df['timestamp'].iloc[0])[:16] + " -> " + str(df['timestamp'].iloc[-1])[:16])
print("Candles: " + str(len(df)) + " | Equivale a ~" + str(round(months, 2)) + " meses")
print()

# ── Parametros a probar ────────────────────────────────────────────────────

# EMA combos: (fast, slow, long)
EMA_COMBOS = [
    (3,  8,  21),   # Ultra-rapido: ideal M5/M15
    (5, 13,  21),   # Actual SCALP H1 (baseline)
    (8, 21,  34),   # Moderado: balance velocidad/ruido
]

# RSI: (period, overbought, oversold)
RSI_COMBOS = [
    (7,  75, 25),   # Muy rapido, bounds amplios (menos restriccion)
    (10, 70, 30),   # Actual SCALP H1 (baseline)
    (14, 65, 35),   # Estandar, mas filtrado
]

# SL/TP: (sl_mult, tp_mult)
SLTP_COMBOS = [
    (0.5, 1.5),   # SL muy estrecho, TP rapido - muchos trades
    (0.8, 2.0),   # Actual SCALP H1 (baseline)
    (1.0, 2.0),   # SL estandar M15
    (0.8, 2.5),   # SL ajustado, TP ambicioso
]

# Filtro de volumen
VOL_COMBOS = [1.0, 1.2]

# ── Ejecutar combinaciones ─────────────────────────────────────────────────
results = []
total = len(EMA_COMBOS) * len(RSI_COMBOS) * len(SLTP_COMBOS) * len(VOL_COMBOS)
count = 0

print("Probando " + str(total) + " combinaciones...")

for ef, es, el in EMA_COMBOS:
    for rp, rob, ros in RSI_COMBOS:
        for sl_m, tp_m in SLTP_COMBOS:
            for vol_m in VOL_COMBOS:
                count += 1
                params = {
                    "ema_fast": ef, "ema_slow": es, "ema_long": el,
                    "rsi_period": rp, "rsi_overbought": rob, "rsi_oversold": ros,
                    "atr_sl_mult": sl_m, "atr_tp_mult": tp_m,
                    "vol_mult": vol_m, "risk_pct": 1.0,
                    "atr_period": 14, "bb_period": 20, "bb_std": 2.0,
                    "vol_sma_period": 50,
                    "preset_name": "M15_TEST",
                    "preset_description": "",
                    "recommended_timeframe": "MINUTE_15",
                }
                bt = BacktestConfig(
                    epic='GOLD', timeframe='MINUTE_15',
                    initial_capital=250.0, risk_pct=1.0,
                    spread_points=0.5, max_candles=1000,
                    strategy=StrategyConfig(**params)
                )
                r = run_backtest(df, bt)
                s = r.stats
                if 'error' in s or s.get('total_trades', 0) < 3:
                    continue

                ret_mo  = round(s['total_return_pct'] / months, 2)
                dd      = abs(s['max_drawdown_pct']) if s['max_drawdown_pct'] != 0 else 1
                pf      = s['profit_factor']
                wr      = s['win_rate_pct']
                trades  = s['total_trades']
                tr_mo   = round(trades / months, 1)
                score   = round((pf * (wr/100) * max(ret_mo, 0)) / dd, 4) if dd > 0 else 0

                results.append({
                    'ema': str(ef)+'/'+str(es)+'/'+str(el),
                    'rsi': str(rp)+'('+str(int(ros))+'-'+str(int(rob))+')',
                    'sl_tp': str(sl_m)+'x/'+str(tp_m)+'x',
                    'vol': vol_m,
                    'trades': trades,
                    'tr_mo': tr_mo,
                    'wr': wr,
                    'pf': pf,
                    'ret_mo': ret_mo,
                    'dd': s['max_drawdown_pct'],
                    'exp': s['expectancy_per_trade'],
                    'score': score,
                })

# ── Resultados ─────────────────────────────────────────────────────────────
results.sort(key=lambda x: x['score'], reverse=True)

print()
print("=" * 80)
print("RESULTADOS M15 | TOP 10 COMBINACIONES | GOLD")
print("=" * 80)
print()

if not results:
    print("Sin resultados validos. Mercado quiza muy lateral en este periodo.")
else:
    # Header
    print(f"{'#':<3} {'EMA':<12} {'RSI':<14} {'SL/TP':<10} {'Vol':<5} "
          f"{'Trades':<8} {'T/mes':<7} {'WR%':<7} {'PF':<6} "
          f"{'Ret/mes':<9} {'MaxDD':<8} {'Exp$':<7} {'Score':<8}")
    print("-" * 105)

    for i, r in enumerate(results[:10], 1):
        verdict = " <<< MEJOR" if i == 1 else (" <<< TOP3" if i <= 3 else "")
        print(f"{i:<3} {r['ema']:<12} {r['rsi']:<14} {r['sl_tp']:<10} {r['vol']:<5} "
              f"{r['trades']:<8} {r['tr_mo']:<7} {r['wr']:<7} {r['pf']:<6} "
              f"{r['ret_mo']:<9} {r['dd']:<8} {r['exp']:<7}{verdict}")

print()
print("=" * 80)

# Comparar con H1 baseline
print()
print("COMPARACION CON BASELINE ACTUAL (SCALP H1)")
print("  H1 SCALP: EMA 5/13/21 | RSI 10(30-70) | SL 0.8x/TP 2.0x | vol 1.2")
print("  H1 result: ~14 trades/mes | WR 42.9% | PF 1.78 | +14.2%/mes | MaxDD -8%")
print()

if results:
    best = results[0]
    print("  MEJOR M15:  EMA " + best['ema'] + " | RSI " + best['rsi']
          + " | SL/TP " + best['sl_tp'] + " | vol " + str(best['vol']))
    print("  M15 result: ~" + str(best['tr_mo']) + " trades/mes | WR " + str(best['wr'])
          + "% | PF " + str(best['pf']) + " | +" + str(best['ret_mo']) + "%/mes"
          + " | MaxDD " + str(best['dd']) + "%")
    print()
    if best['tr_mo'] > 14:
        diff = round(best['tr_mo'] - 14, 1)
        print("  Frecuencia: +" + str(diff) + " trades/mes mas que H1")
    if best['ret_mo'] > 14.2:
        print("  Rendimiento: MEJOR que H1 SCALP")
    elif best['ret_mo'] > 8:
        print("  Rendimiento: COMPARABLE a H1 SCALP")
    else:
        print("  Rendimiento: INFERIOR a H1 SCALP - recomendar mantener H1")

print()
print("NOTA: Backtest sobre ~" + str(round(months * 30, 0)) + " dias. "
      + "Minimo recomendado para decision: 3 meses de datos.")
print("Los resultados M15 pueden ser menos estables por mayor ruido en timeframes cortos.")
print("=" * 80)
