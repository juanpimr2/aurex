# 🔧 Aurex — Auditoría Técnica

> Responsable técnico: revisión del 26-jun-2026. Documento vivo: actualizar tras cada mejora.
> Alcance: fiabilidad, trazabilidad, persistencia, seguridad. **No** cambia estrategia ni dinero.

---

## 1. Mapa del sistema (cómo funciona hoy)

```
                    ┌──────────────────────────────────────────┐
                    │   SESIÓN CLAUDE CODE (en este PC)         │
                    │   Crons en memoria (CronCreate)           │  ← PUNTO ÚNICO DE FALLO
                    └──────────────┬───────────────────────────┘
                                   │ dispara cada X min
          ┌────────────────────────┼────────────────────────┐
          ▼                        ▼                        ▼
   monitor_swing.py        monitor_scalp.py        monitor_m15_obs.py
   (DAY + H4)              (H1 + H4)               (M15 + H4)
          │                        │                        │
          │   ── todos usan ──     │                        │
          ▼                        ▼                        ▼
   capital_client.py  →  API REST Capital.com  (login, precios, abrir/cerrar/modificar)
   strategy.py        →  indicadores + señales (EMA/RSI/BB/ATR)
   smc_filters.py     →  estructura SMC (FVG/OB/BoS/CHoCH)
   macro_context.py   →  calendario FOMC/NFP (solo contexto)

   PERSISTENCIA (fragmentada):
   ├─ aurex_trades.db   (SQLite)  ← SOLO M15 escribe aquí
   ├─ swing_signal_log.csv        ← SWING
   ├─ m15_signal_log.csv          ← M15
   ├─ trade_log.csv               ← SCALP (casi vacío)
   ├─ m15_trade_state.json        ← estado posición M15 abierta
   └─ daily_reports/*.txt         ← reportes diarios

   REPORTING:
   └─ session_report_daily.py  (cron 23:03) → lee los logs y genera informe
```

**Vía paralela NO usada por los crons:** `main.py` (FastAPI) + `trader.py` (LiveTrader) son un segundo motor de trading independiente. Hoy la operativa real va por los `monitor_*.py`. `main.py/trader.py` parecen legado → riesgo de confusión.

**Protección del dinero:** SL y TP se fijan en el broker al abrir. Por eso las posiciones sobreviven aunque el PC se reinicie (verificado: 2 reinicios el 24-jun, posición intacta). Lo que NO sobrevive es la **gestión/monitorización** (trailing, reportes) mientras el sistema está caído.

---

## 2. Riesgos técnicos por impacto

| # | Riesgo | Impacto | Estado |
|---|--------|---------|--------|
| R1 | **Scheduling = punto único de fallo.** Los "crons" viven en la sesión Claude (memoria). Si el PC/sesión cae, no corre nada y se pierden al reiniciar. | ALTO | Abierto |
| R2 | **Sin backup verificado fuera del PC.** `aurex_trades.db` está gitignored; solo OneDrive da redundancia accidental, sin verificación de integridad ni versionado. | ALTO | **Mitigado parcial** (script `backup_aurex.py`) |
| R3 | **Persistencia fragmentada e inconsistente.** 5 almacenes distintos; la BD SQLite solo la usa M15. No hay fuente única de verdad. | ALTO | Abierto |
| R4 | **Errores silenciosos.** Los monitores hacen `print` y `sys.exit`; no hay logs persistentes, ni captura de excepciones, ni alertas. Un fallo de API (timeout de login) pasa desapercibido si no hay humano mirando. | ALTO | Abierto |
| R5 | **Sin tests.** Cero cobertura en cálculo de señales, gestión de riesgo, persistencia y auto-cierre. Un cambio puede romper algo sin avisar. | MEDIO | Abierto |
| R6 | **Código duplicado.** `auto_close_swing_trades` estaba duplicado en swing y scalp (mismo bug en ambos). Probable más duplicación (indicadores, logging). | MEDIO | Parcial |
| R7 | **`.env` con credenciales en carpeta OneDrive.** No está en git (correcto), pero sí se sincroniza a la nube de OneDrive. Aceptable para uso personal, a vigilar. | MEDIO | Abierto |
| R8 | **Vía muerta `main.py`/`trader.py`.** Motor paralelo no usado; si se ejecuta por error podría operar con otra lógica. | BAJO | Abierto |
| R9 | **Reporting leía log vacío** (mostraba cifras fantasma). | — | ✅ Resuelto 26-jun |
| R10 | **Auto-cierre inventaba P&L $0.00** sin `eq_open`. | — | ✅ Resuelto 26-jun |

---

## 3. Qué datos se guardan, dónde y cuánto

| Dato | Fichero | Quién escribe | Retención | Backup |
|------|---------|---------------|-----------|--------|
| Trades reales (open) | `aurex_trades.db` (SQLite) | Solo M15 | Indefinida (local) | Solo OneDrive (accidental) |
| Señales/trades SWING | `swing_signal_log.csv` | SWING | Indefinida | OneDrive + git |
| Señales/trades M15 | `m15_signal_log.csv` | M15 | Indefinida | OneDrive + git |
| Trades SCALP | `trade_log.csv` | SCALP | Indefinida (vacío) | OneDrive + git |
| Estado posición M15 | `m15_trade_state.json` | M15 | Se sobrescribe | OneDrive + git |
| Reportes diarios | `daily_reports/*.txt` | Reporte diario | Indefinida | OneDrive + git |

**Problema:** no hay una política de retención ni un backup íntegro y verificado del **año de prueba**. La BD (el dato más valioso) es justo la que no entra en git.

---

## 4. Propuesta de backup / persistencia cloud (gratis o casi)

**Capa 0 — local verificado (ya implementado):** `backup_aurex.py` copia DB+CSVs+reportes a `backups/` con `manifest.json` (hash SHA256 + tamaño) y verifica integridad. **Nunca copia `.env`.**

**Capa 1 — OneDrive (ya activo, gratis):** el proyecto vive en `OneDrive\Escritorio\...`, así que OneDrive ya sincroniza todo a la nube. Acción: confirmar que la carpeta `backups/` se sincroniza y que OneDrive tiene espacio. Coste: 0 (plan existente).

**Capa 2 — Git para datos versionados (gratis):** los CSV y reportes ya van a GitHub (`juanpimr2/aurex`). Falta versionar la BD. Opción: exportar la BD a un CSV/SQL dump y commitearlo (los binarios `.db` no van bien en git, pero un dump de texto sí).

**Capa 3 — Cloud independiente del PC (recomendado, gratis):**
| Opción | Coste | Pros | Contras |
|--------|-------|------|---------|
| **Google Drive** (rclone o API) | Gratis 15 GB | Independiente de OneDrive, fácil | Requiere configurar credenciales OAuth (NO subir a git) |
| **GitHub** (dump SQL del .db) | Gratis | Ya lo usamos, versionado | No apto para binarios grandes |
| **Cloudflare R2 / Backblaze B2** | ~0€ a este volumen | S3-compatible, robusto | Más setup |

**Recomendación:** mantener **OneDrive (capa 1) + dump de la BD a git (capa 2)** como base inmediata (coste 0, ya disponible), y añadir **Google Drive vía rclone (capa 3)** como copia independiente cuando quieras redundancia real fuera de Microsoft. Las credenciales de Drive irían en `.env` (gitignored), nunca en el repo.

---

## 5. Backlog priorizado

### 🔴 Urgente / riesgo alto
- [ ] **B1. Scheduler resiliente del SO** (Task Scheduler de Windows) que lance los monitores aunque la sesión Claude no esté → elimina R1. *(Cambia infraestructura, no estrategia. Requiere tu OK.)*
- [x] **B2. Logging estructurado + captura de errores** — `aurex_logger.py` (log mensual) + `run_monitor.py` (wrapper que ejecuta cada monitor capturando salida/errores/duración sin tocar su código). → mitiga R4. *(Hecho 26-jun)*
- [x] **B3. Backup automático diario** — `daily_backup.py` + `backup_aurex.py` (backup verificado + poda). Falta activar el cron diario. → cierra R2. *(Hecho 26-jun)*
- [x] **B4. Dump de la BD a git** — `dump_db.py` → `aurex_trades_dump.csv` versionable. → cierra R2. *(Hecho 26-jun)*

### 🟡 Importante
- [ ] **B5. Unificar persistencia:** que SWING y SCALP también escriban en `aurex_trades.db` (fuente única). → R3.
- [ ] **B6. Cron de mantenimiento técnico diario** (solo lectura): revisa logs, detecta excepciones/anomalías/monitores que no corrieron, y genera informe técnico. NO toca estrategia ni dinero. → R4.
- [ ] **B7. Tests** de: cálculo de indicadores/señales, sizing/riesgo, auto-cierre, parsing de logs. → R5.
- [ ] **B8. Validaciones de datos:** API caída, respuesta inválida, velas incompletas, NaN, duplicados → modo seguro (no operar). → R4.
- [ ] **B9. Idempotencia anti-duplicados:** evitar que dos ejecuciones casi simultáneas abran 2 trades. → R4.

### 🟢 Mejoras futuras
- [ ] B10. Eliminar o aislar la vía muerta `main.py`/`trader.py`. → R8.
- [ ] B11. Refactor de duplicación (indicadores, auto-cierre, logging a un módulo común). → R6.
- [ ] B12. Roles analíticos auditables (tendencia/volatilidad/volumen/riesgo) con confianza + invalidación, separados de ejecución.
- [ ] B13. Reporte semanal automático legible.
- [ ] B14. Mover credenciales a un gestor de secretos del SO (Windows Credential Manager).

---

## 6. Primer conjunto de cambios SEGUROS (sin tocar estrategia ni dinero)

| Cambio | Estado | Riesgo trading |
|--------|--------|----------------|
| Reporte diario consolida los 3 logs + quita cifras fantasma | ✅ Hecho (26-jun) | Ninguno (solo lectura) |
| Auto-cierre no inventa P&L $0.00 | ✅ Hecho (26-jun) | Ninguno (solo logging) |
| `backup_aurex.py` (backup + integridad) | ✅ Hecho (26-jun) | Ninguno (solo copia) |
| B2 Logging estructurado | Propuesto | Ninguno (solo añade logs) |
| B3/B4 Backup diario + dump BD a git | Propuesto | Ninguno |
| B6 Cron de mantenimiento (solo lectura) | Propuesto | Ninguno |

**Requieren tu aprobación explícita** (tocan infraestructura/ejecución): B1 (Task Scheduler), B5 (escritura en BD desde swing/scalp), B8/B9 (validaciones que pueden bloquear operaciones).

---

## 7. Registro de cambios de ESTRATEGIA (aprobados por el usuario)

| Fecha | Cambio | Respaldo | Aprobación |
|-------|--------|----------|------------|
| 01-jul-2026 | **SWING: TP `atr_tp_mult` 2.5 → 3.5×ATR** (R:R 1:1.25 → 1:1.75). SL (2.0×) y riesgo (5%) intactos. | Backtest R:R (`bt_rr_swing.py`, 27 meses): la franja de TP amplio supera al actual de forma robusta (PF 2.0→3.01). Walk-forward (`bt_wf_swing.py`, 4 tramos): la propuesta gana en 3/4 tramos y pierde menos en el peor; MaxDD idéntico (SL sin cambiar). | ✅ Usuario, 01-jul-2026 |

**Razón:** SWING captura tendencias largas del oro; el TP 2.5× cortaba las ganancias demasiado pronto. Ampliar solo el TP deja correr los trades sin añadir riesgo (SL fijo). Ampliar el SL se descartó por datos (empeora). Solo afecta a trades SWING **futuros**; no había posición abierta al aplicarlo.

---

*Mantener este documento al día. Cada cambio: analizar → verificar → documentar → probar → registrar.*
