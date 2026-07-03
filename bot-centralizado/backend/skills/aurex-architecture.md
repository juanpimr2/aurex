# Skill: Arquitectura de Aurex

> Para cualquier agente/dev que aterrice en el repo. Actualizar si cambia la estructura.

## Qué es
Bot de trading automatizado sobre **GOLD (XAUUSD)** en Capital.com (CFD, cuenta **EUR**).
Decisiones 100% por reglas deterministas. Claude supervisa/reporta, **nunca decide trades**.

## Ruta de producción (lo único que opera dinero)
```
Crons (sesión Claude, cada 15/30 min L-V)
  └─ run_monitor.py <monitor>        # wrapper: logging B2 + captura errores
       ├─ monitor_m15_obs.py         # M15 REAL, riesgo 2%, filtro ATR>SMA50
       ├─ monitor_scalp.py           # H1 REAL, riesgo 1% + auto-close de los 3 logs
       └─ monitor_swing.py           # DAY REAL, riesgo 5%, filtro H4, SMC, macro
Módulos compartidos: capital_client.py · strategy.py · smc_filters.py · macro_context.py · db.py
```

## Datos (fuentes de verdad)
| Qué | Dónde | Nota |
|-----|-------|------|
| **P&L real de cierres** | tabla `trade_closes` (via `reconcile.py`) | LA verdad — viene del broker por dealId |
| Aperturas M15 | tabla `trades` (db.py) | solo M15 escribe (B5 pendiente) |
| Señales/cierres estimados | `m15_signal_log.csv`, `swing_signal_log.csv` | etiquetas TP/SL son estimación (H1 auditoría) |
| Velas propias | tabla `candles` (`collect_candles.py`, diario 23:10) | única vía para backtest M15/H1 futuro |
| Snapshots para backtest | `research/data_snapshots/*.csv` | backtests SIEMPRE sobre snapshot, no API viva |

## Baseline y validación
- Baseline oficial: `research/baseline_metrics.json` (correr `research/baseline_swing.py`).
- Cambio de estrategia = backtest + walk-forward + aprobación explícita del usuario
  + registro en `docs/AUDITORIA_TECNICA.md` §7. Sin excepciones.

## Salud y observabilidad
- `health_check.py` → veredicto SANO/AVISOS/CRITICO (exit 0/1/2). Correr a diario.
- Logs: `logs/aurex_YYYY-MM.log`. Dashboard solo-lectura: `python dashboard.py` → :8181.
- Backup diario verificado: `daily_backup.py` (23:10) + push datos a git.

## No tocar / saber
- `legacy/` = motor paralelo muerto. NO ejecutar.
- Posiciones no-GOLD (ej. NVDA) = manuales del usuario. Ignorar siempre.
- Crons viven en la sesión Claude (punto único de fallo — B1 pendiente).
- Docs clave: `docs/AUDITORIA_TECNICA.md`, `docs/AUDITORIA_FASE0.md`, `docs/TRASPASO_SESION.md`.
