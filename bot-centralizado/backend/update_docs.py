# -*- coding: utf-8 -*-
"""
update_docs.py - Aurex
Actualiza automaticamente docs/REGISTRO_CUENTA.md con el historial real de trades.
Ejecutar manualmente o anadir al reporte diario.
"""
import os, csv
from datetime import date

LOG_PATH   = os.path.join(os.path.dirname(__file__), 'trade_log.csv')
DOCS_PATH  = os.path.join(os.path.dirname(__file__), 'docs', 'REGISTRO_CUENTA.md')
CAPITAL_INICIAL = 250.0

if not os.path.exists(LOG_PATH):
    print("Sin trade_log.csv — nada que actualizar.")
    exit(0)

with open(LOG_PATH, newline='', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))

trades = [r for r in rows if r.get('result','').upper() in ('TP','SL','OPEN')]
cerrados = [r for r in trades if r.get('result','').upper() in ('TP','SL')]
tp_total = sum(1 for r in cerrados if r.get('result','').upper() == 'TP')
sl_total = sum(1 for r in cerrados if r.get('result','').upper() == 'SL')
pnl_total = sum(float(r.get('pnl_usd') or 0) for r in cerrados)
wr = round(tp_total / len(cerrados) * 100, 1) if cerrados else 0.0

# Balance actual = ultimo balance_after disponible
balance_actual = CAPITAL_INICIAL
for r in reversed(trades):
    try:
        b = float(r.get('balance_after') or 0)
        if b > 0:
            balance_actual = b
            break
    except Exception:
        pass

mejor_trade = max(cerrados, key=lambda r: float(r.get('pnl_usd') or 0), default=None)
peor_trade  = min(cerrados, key=lambda r: float(r.get('pnl_usd') or 0), default=None)

# Profit Factor
ganancias = sum(float(r.get('pnl_usd') or 0) for r in cerrados if float(r.get('pnl_usd') or 0) > 0)
perdidas  = abs(sum(float(r.get('pnl_usd') or 0) for r in cerrados if float(r.get('pnl_usd') or 0) < 0))
pf = round(ganancias / perdidas, 2) if perdidas > 0 else 0.0

# Tabla de trades
tabla = ""
for i, r in enumerate(trades, 1):
    fecha  = r.get('date', '?')
    direc  = r.get('direction', '?')
    entry  = r.get('entry', '?')
    sl     = r.get('sl', '?')
    tp_v   = r.get('tp', '?')
    size   = r.get('size', '?')
    pnl    = r.get('pnl_usd', '')
    result = r.get('result', '?')
    bal    = r.get('balance_after', '?')
    notes  = (r.get('notes', '') or '')[:60]
    pnl_str = ("+" if float(pnl) > 0 else "") + "$" + str(pnl) if pnl else "abierto"
    tabla += f"| {i} | {fecha} | {direc} | {entry} | {sl} | {tp_v} | {size} | {pnl_str} | {result} | ${bal} |\n"

# Balance ASCII chart
balances = []
for r in trades:
    try:
        b = float(r.get('balance_after') or 0)
        if b > 0:
            balances.append((r.get('date',''), b))
    except Exception:
        pass

chart = ""
if balances:
    max_b = max(b for _, b in balances)
    min_b = min(b for _, b in balances)
    rows_chart = 5
    step = (max_b - min_b) / rows_chart if max_b != min_b else 1
    for row_i in range(rows_chart, -1, -1):
        level = min_b + row_i * step
        line = f"${round(level,0):5.0f} |"
        for _, b in balances:
            if b >= level - step * 0.5:
                line += " ●"
            else:
                line += "  "
        chart += line + "\n"
    chart += "       " + "  ".join([d[-5:] for d, _ in balances]) + "\n"

# Lecciones por mes
lecciones = {
    "13 Apr": ("Precio sube tras SELL — SL ejecutado correctamente.", "Sistema validado."),
    "15 Apr": ("2 SL consecutivos BUY — caida brusca NY.", "Mejorado filtro H4 + cooling-off."),
    "16 Apr": ("Re-entrada rapida tras SL — mercado bajista continuo.", "Salvaguarda cooling-off implementada."),
}

contenido = f"""# AUREX — REGISTRO HISTORICO DE CUENTA
> Actualizado automaticamente: {date.today().isoformat()} | Fuente: trade_log.csv

---

## HISTORIAL DE TRADES

| # | Fecha | Dir | Entry | SL | TP | Size | P&L | Result | Balance |
|---|-------|-----|-------|----|----|------|-----|--------|---------|
{tabla}
---

## METRICAS ACUMULADAS

| Metrica | Valor |
|---------|-------|
| Capital inicial | ${CAPITAL_INICIAL:.2f} |
| Balance actual | **${balance_actual:.2f}** |
| P&L total | **${pnl_total:+.2f}** ({round((balance_actual-CAPITAL_INICIAL)/CAPITAL_INICIAL*100,2)}%) |
| Trades totales | {len(trades)} |
| Cerrados | {len(cerrados)} (TP: {tp_total} / SL: {sl_total}) |
| Abiertos ahora | {len(trades)-len(cerrados)} |
| Win Rate | **{wr}%** |
| Profit Factor | {pf} |
| Mejor trade | {("+" + "$" + str(float(mejor_trade.get("pnl_usd",0))) if mejor_trade else "N/A")} |
| Peor trade | {("$" + str(float(peor_trade.get("pnl_usd",0))) if peor_trade else "N/A")} |

> Con {len(cerrados)} trades cerrados la muestra es {'pequena — necesitamos 30+ para validar estadisticamente' if len(cerrados) < 30 else 'suficiente para analisis estadistico'}.

---

## EVOLUCION DEL BALANCE

```
{chart}```

---

## LECCIONES APRENDIDAS

| Fecha | Fallo | Lectura | Accion tomada |
|-------|-------|---------|---------------|
"""

for fecha, (fallo, accion) in lecciones.items():
    contenido += f"| {fecha} | {fallo} | {accion} | Implementado |\n"

contenido += "\n---\n\n*Generado automaticamente por update_docs.py*\n"

os.makedirs(os.path.dirname(DOCS_PATH), exist_ok=True)
with open(DOCS_PATH, 'w', encoding='utf-8') as f:
    f.write(contenido)

print("REGISTRO_CUENTA.md actualizado.")
print(f"  Trades: {len(trades)} | TP: {tp_total} | SL: {sl_total} | WR: {wr}% | PF: {pf}")
print(f"  Balance: ${balance_actual:.2f} | P&L: ${pnl_total:+.2f}")
