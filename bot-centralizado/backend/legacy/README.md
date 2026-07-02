# ⚠️ Código LEGADO — NO EJECUTAR en producción

Movido aquí el 2026-07-02 (Fase 1, elimina riesgo R8 de la auditoría).

Estos módulos son una **vía paralela de trading NO usada por los crons** de
producción. Contienen lógica de órdenes propia y desactualizada: ejecutarlos
por error podría operar con parámetros distintos a los validados.

| Fichero | Qué era |
|---------|---------|
| `main.py` | Servidor FastAPI con endpoints de trading (motor paralelo) |
| `trader.py` | LiveTrader — bucle de trading alternativo usado por main.py |
| `open_trade.py` | Script manual de apertura de posiciones |
| `session_review.py` | Análisis de sesión antiguo (reemplazado por session_report_daily.py) |
| `update_docs.py` | Actualizador de documentación antiguo |

**La producción real** son los `monitor_*.py` ejecutados vía `run_monitor.py`
por los crons. Ver `docs/AUDITORIA_TECNICA.md` y `docs/AUDITORIA_FASE0.md`.

Si algún día se quiere una API/panel, se construirá sobre la ruta de producción
actual, no sobre este código.
