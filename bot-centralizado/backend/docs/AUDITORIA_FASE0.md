# 🔬 Aurex — Auditoría Fase 0 (técnica + cuantitativa)

> Fecha: 2026-07-02 · Solo lectura: nada de esto tocó estrategia, órdenes ni dinero.
> Complementa `AUDITORIA_TECNICA.md` (26-jun). Baseline en `research/baseline_metrics.json`.

---

## 1. Inventario de módulos (F0.1)

**Ruta de producción (lo que ejecutan los crons):**
```
run_monitor.py (wrapper logging)
 ├─ monitor_swing.py  → capital_client, strategy, smc_filters, macro_context
 ├─ monitor_scalp.py  → capital_client, strategy        [+ auto-close de los 3 logs]
 └─ monitor_m15_obs.py→ capital_client, strategy, db    [ÚNICO que escribe en SQLite]
session_report_daily.py (reporte 23:03) · daily_backup.py → dump_db + backup_aurex (23:10)
```

**Investigación:** `backtester.py` + 7 scripts `bt_*` + `research/` (nuevo).
**Código muerto / legado (NO usado por crons):** `main.py` (FastAPI, 635 líneas), `trader.py` (202), `open_trade.py`, `session_review.py`, `update_docs.py` → ~1.150 líneas de vía paralela con lógica de trading propia. **Riesgo R8**: si alguien lo ejecuta, opera con otra lógica. Candidato a aislar en `legacy/` (Fase 1).

Total backend: ~5.600 líneas Python en 27 ficheros. Sin tests (0 líneas).

---

## 2. Auditoría técnica de rutas críticas (F0.2) — hallazgos

| # | Hallazgo | Severidad | Detalle |
|---|----------|-----------|---------|
| **H1** | **Etiquetado TP/SL del auto-cierre no es fiable** | 🔴 ALTA (calidad de datos) | `monitor_scalp.py:167` — si `equity_now - eq_open >= 0` etiqueta **'TP'**, si <0 'SL'. Un cierre manual, breakeven o anticipado con equity positivo queda como "TP". Además el P&L por diferencia de equity está **contaminado por el drift de NVDA** (posición externa). Evidencia: SWING 16-jun registró TP +$12.74 (esperado a TP real: ~$22.6) y 24-jun TP +$2.80 (esperado ~$24.5) — ninguno coincide con su TP teórico → **el "2 TP / 0 SL (WR 100%)" de SWING es etiquetado optimista**; lo defendible es "+$15.54 aprox. en 2 cierres positivos". |
| **H2** | Riesgo abierto mal calculado | 🟡 MEDIA (conservador) | `monitor_scalp.py:509` — `riesgo_abierto = len(positions) × equity × RISK_PCT` cuenta TODAS las posiciones (incluida NVDA manual) a riesgo plano, en vez de sumar el riesgo real por distancia a SL de las posiciones Aurex. Err a favor de bloquear antes (seguro), pero es impreciso. |
| **H3** | Hueco de reconciliación en `open_position` | 🟡 MEDIA | `capital_client.py:168-183` — si la orden se acepta pero el GET `/confirms` falla (timeout), devuelve `None`: el monitor cree que falló y **no escribe la fila OPEN en el log** → posición viva sin tracking (quedaría como "externa"). Mitigado en parte por el anti-duplicado. Falta reconciliación broker↔log por deal_id. |
| **H4** | Sin retry/backoff ni manejo 429 | 🟡 MEDIA | Los "Read timed out" de login son recurrentes en producción; cada fallo = ciclo de monitor perdido. Un retry con backoff (2 intentos) lo resolvería. |
| **H5** | La BD solo registra APERTURAS y solo de M15 | 🟡 MEDIA | `db.py` no tiene columnas de cierre/PnL; los cierres viven en notas de CSV. No hay fuente única de verdad para trades ida-y-vuelta (= B5 + extensión). |
| **H6** | Precios solo BID | 🟢 BAJA | `get_prices` usa bid para OHLC; el spread solo se modela en backtest (0.5 pts fijo). Para GOLD es aceptable; verificar spread real por `get_market_info` en Fase 1. |
| **H7** | Bug fecha NFP | 🟢 BAJA (conocido) | `macro_context.py` asume "primer viernes"; el NFP del 2-jul-2026 salió jueves (festivo 4-jul). Solo informativo. |

**Lo que está BIEN construido:** SL+TP siempre en broker (sobrevivió a 2 reinicios reales) · fix del TP-wipe en `modify_position` con preservación de niveles · anti-duplicado por epic+dirección · cadena de salvaguardas (viernes, H4, DD, stop diario, cooling-off) implementada de verdad · filtro ATR dinámico en M15 demostró valor en producción (30-jun: 4 SELL bloqueadas que habrían perdido) · logging B2 + backup B3/B4 operativos.

---

## 3. Límites reales de datos (F0.3) — snapshot 2026-07-02

| TF | Velas | Rango | Backtesteable |
|----|-------|-------|---------------|
| DAY | 1000 | 2023-04-18 → 2026-07-02 (**39 meses**) | ✅ Sí (única base sólida) |
| H4 | 1000 | 2025-11-14 → hoy (230 días) | ⚠️ Marginal |
| H1 | 1000 | 2026-05-01 → hoy (61 días) | ❌ No |
| M15 | 1000 | 2026-06-17 → hoy (**15 días**) | ❌ No |

**Implicación dura:** las estrategias M15 y SCALP **no se pueden validar** con datos de la API. La única vía es **persistir velas nosotros mismos** (job diario que acumule H1/M15 en la BD) → en 2-3 meses habrá muestra propia. Recomendado para Fase 1.
Snapshots en `research/data_snapshots/` + manifest → todo backtest futuro debe correr sobre snapshot, no sobre API viva.

---

## 4. Baseline cuantitativo reproducible (F0.4)

**Config exacta de producción** (EMA 8/21/50 · RSI 14 35-65 · SL 2.0×ATR · **TP 3.5×ATR** · riesgo 5% · spread 0.5):

| Métrica | Valor (39 meses, 1000 velas DAY) |
|---------|------------------------|
| Trades | 30 |
| Win rate | 56.7% |
| Profit factor | 2.34 |
| Retorno total | +110.1% (~2.8%/mes compuesto) |
| **Max drawdown** | **23.1%** ⚠️ |
| Expectancy | $9.18/trade |
| Avg win / loss | $28.24 / −$15.75 |

**Hallazgo honesto (H8):** el MaxDD histórico a riesgo 5% es **23.1%**, no el ~10% que daba la ventana de 27 meses usada el 1-jul. Los datos de 2023-2024 (régimen menos tendencial) castigan más. Con 5% de riesgo por trade, una cuenta de $650 puede ver un valle de ~$150. **El riesgo 5% se mantiene por decisión del usuario**, pero este número debe estar sobre la mesa en cualquier conversación de sizing futura.

**Realidad live (8 trades reales):** M15 2TP/3SL −$2.18 (fiable, deal_id + eq_open) · SWING ~+$15.54 en 2 cierres positivos (etiquetas TP dudosas, ver H1) · SCALP 0 trades. Muestra demasiado pequeña para concluir nada; coherente en signo con el baseline.

---

## 5. Recomendaciones priorizadas para Fase 1

1. **Persistencia de velas propia** (job diario read-only → BD) — desbloquea validar M15/SCALP en el futuro. Sin esto, scalping quedará no-validable para siempre.
2. **Reconciliación broker↔logs por deal_id + cierres en BD** (arregla H1, H3, H5): tabla `trade_closes` con precio real de cierre del broker, no estimación por equity. Elimina el etiquetado TP/SL optimista.
3. **Retry/backoff en capital_client** (H4) — 2 reintentos con espera; menos ciclos perdidos.
4. **B1 Task Scheduler del SO** — sigue siendo el punto único de fallo #1 (requiere OK del usuario).
5. **Aislar legado** `main.py`/`trader.py` → `legacy/` (elimina R8).
6. Tests: empezar por sizing, señales y auto-cierre (lo que toca dinero).

*Ninguna de estas recomendaciones cambia la estrategia. Las que tocan ejecución/live (2, 3, 4) se implementarán con validación y se activarán con OK del usuario.*
