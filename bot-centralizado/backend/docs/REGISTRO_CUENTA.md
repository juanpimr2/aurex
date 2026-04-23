# AUREX — REGISTRO HISTORICO DE CUENTA
> Actualizado automaticamente: 2026-04-23 | Fuente: trade_log.csv

---

## HISTORIAL DE TRADES

| # | Fecha | Dir | Entry | SL | TP | Size | P&L | Result | Balance |
|---|-------|-----|-------|----|----|------|-----|--------|---------|
| 1 | 2026-04-13 | SELL | 4730.09 | 4755.63 | 4696.62 | 0.1 | $-2.22 | SL | $247.78 |
| 2 | 2026-04-15 | BUY | 4825.04 | 4811.64 | 4858.54 | 0.18 | $-2.35 | SL | $245.43 |
| 3 | 2026-04-15 | BUY | 4798.09 | 4783.88 | 4833.61 | 0.17 | $-1.64 | SL | $243.79 |
| 4 | 2026-04-16 | BUY | 4794.41 | 4783.88 | 4833.61 | 0.17 | +$6.6 | TP | $251.79 |
| 5 | 2026-04-16 | BUY | 4815.33 | 4805.46 | 4840.0 | 0.26 | $-2.64 | SL | $249.15 |
| 6 | 2026-04-16 | BUY | 4793.95 | 4784.08 | 4818.62 | 0.25 | $-2.87 | SL | $246.28 |

---

## METRICAS ACUMULADAS

| Metrica | Valor |
|---------|-------|
| Capital inicial | $250.00 |
| Balance actual | **$246.28** |
| P&L total | **$-5.12** (-1.49%) |
| Trades totales | 6 |
| Cerrados | 6 (TP: 1 / SL: 5) |
| Abiertos ahora | 0 |
| Win Rate | **16.7%** |
| Profit Factor | 0.56 |
| Mejor trade | +$6.6 |
| Peor trade | $-2.87 |

> Con 6 trades cerrados la muestra es pequena — necesitamos 30+ para validar estadisticamente.

---

## EVOLUCION DEL BALANCE

```
$  252 |       ●    
$  250 |       ●    
$  249 |       ● ●  
$  247 | ●     ● ● ●
$  245 | ● ●   ● ● ●
$  244 | ● ● ● ● ● ●
       04-13  04-15  04-15  04-16  04-16  04-16
```

---

## LECCIONES APRENDIDAS

| Fecha | Fallo | Lectura | Accion tomada |
|-------|-------|---------|---------------|
| 13 Apr | Precio sube tras SELL — SL ejecutado correctamente. | Sistema validado. | Implementado |
| 15 Apr | 2 SL consecutivos BUY — caida brusca NY. | Mejorado filtro H4 + cooling-off. | Implementado |
| 16 Apr | Re-entrada rapida tras SL — mercado bajista continuo. | Salvaguarda cooling-off implementada. | Implementado |

---

*Generado automaticamente por update_docs.py*
