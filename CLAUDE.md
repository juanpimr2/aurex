# Aurex — Sistema de Trading Automatizado

## Contexto del proyecto
Bot de scalping automatizado sobre GOLD (XAUUSD) en Capital.com.
Usuario novato, capital limitado. El objetivo es operar de forma disciplinada y automatizada.
Directorio backend: `C:\Users\sagas\OneDrive\Escritorio\Documentos\BotMillonario\bot-centralizado\backend`

---

## Estado de la cuenta
- **Capital inicial:** $250.00
- **Balance actual:** $246.28 (actualizado 16 Apr 2026)
- **Trades realizados:** 6 (ver trade_log.csv en el backend)
- **P&L neto:** -$3.72 (-1.49%)
- **Historial:** SELL -$2.22 | BUY -$2.35 | BUY -$1.64 | BUY +$6.60 (TP) | BUY -$2.64 | BUY -$2.87
- **Objetivo mensual:** 10-15% (~$25-37/mes). 20% posible en meses con tendencia fuerte.

---

## Sistema de 3 niveles (activo desde 17 Apr 2026)

| Nivel | Monitor | TF | Dinero real | Objetivo |
|-------|---------|-----|-------------|----------|
| 1 — SWING | monitor_swing.py | DAY + H4 | Observacion (→ real en ~2 semanas) | Captura tendencias $30-150 |
| 2 — SCALP | monitor_scalp.py | H1 + H4 | ✅ Real | Ganancias diarias $3-8 |
| 3 — M15 OBS | monitor_m15_obs.py | M15 | Paper trading | Validacion 3-4 semanas |

**Regla de coordinacion:** SWING tiene prioridad. Cuando SWING active modo real, SCALP queda bloqueado mientras haya posicion SWING abierta. Un trade a la vez.

---

## Estrategia activa: SCALP H1

| Parámetro | Valor | Razón |
|-----------|-------|-------|
| Instrumento | GOLD (epic: `GOLD`) | CFD Capital.com |
| Timeframe principal | H1 (HOUR) | Señal de entrada |
| Timeframe confirmación | H4 (HOUR_4) | Filtro de tendencia |
| EMAs | 5 / 13 / 21 | Alineación rápida |
| RSI periodo | 10 | Más reactivo para scalp |
| RSI límites | 30 / 70 | Evita sobrecompra/venta |
| SL | **0.8 × ATR** | R:R 1:2.5 — backtest óptimo |
| TP | **2.0 × ATR** | |
| Risk por trade | **1%** del equity | ~$2.50 con $250 |
| Bollinger | 20 periodos, 2 desv. | Filtro de precio dentro de banda |
| Volumen | > 1.2 × SMA(20) | Confirma actividad real |

**Backtest (13 meses H1 GOLD):** 42.9% Win Rate | PF 1.72 | ~12.7%/mes | MaxDD 7%

---

## Salvaguardas del monitor (monitor_scalp.py)

1. **Cierre de semana:** Viernes después de las 17:00 Madrid → NO abre trades
2. **Conflicto H4:** Si H4 contradice la dirección de H1, NO opera
3. **No duplicar dirección:** Si ya hay SELL abierto, no abre otro SELL en GOLD
4. **Max riesgo abierto:** 5% del equity simultáneo (~5 trades max)
5. **Pausa por drawdown abierto:** Si PnL abierto < -10% del equity, para de abrir
6. **Stop diario:** Si P&L del día < -5% del equity (~$12.30), NO opera más ese día
7. **Cooling-off tras SL:** Si hubo SL hoy en misma dirección, exige RSI 35-65 y EMAs alineadas antes de re-entrar
8. **SL + TP siempre fijados:** Nunca posición sin protección en el broker
9. **Noticias:** Solo contexto de referencia, NUNCA trigger de operación

---

## Crons (recrear al inicio de cada sesión diciendo "recrea los crons")

### Monitor SCALP H1 — 24/5
- **Schedule:** `*/30 * * * 1-5` (cada 30 min, lunes a viernes)
- **Prompt:** `Ejecuta el monitor de Aurex con: cd C:\Users\sagas\OneDrive\Escritorio\Documentos\BotMillonario\bot-centralizado\backend && python monitor_scalp.py — luego muestra el resultado completo al usuario en español.`

### Monitor M15 Observacion — 24/5
- **Schedule:** `*/15 * * * 1-5` (cada 15 min, lunes a viernes)
- **Prompt:** `Ejecuta el monitor M15 de observacion de Aurex con: cd C:\Users\sagas\OneDrive\Escritorio\Documentos\BotMillonario\bot-centralizado\backend && python monitor_m15_obs.py — luego muestra el resultado completo al usuario en español. Si hay senal, indica claramente que es MODO OBSERVACION (no se ejecuta dinero real) y menciona que queda registrada en m15_signal_log.csv.`

### Reporte diario de sesion — Cierre (23:03 Madrid)
- **Schedule:** `3 23 * * 1-5` (lunes a viernes a las 23:03 hora local)
- **Prompt:** `Es el cierre de sesion de Aurex (23:03 Madrid). Ejecuta el reporte diario con: cd C:\Users\sagas\OneDrive\Escritorio\Documentos\BotMillonario\bot-centralizado\backend && python session_report_daily.py 2>&1 | head -80 — luego muestra el resultado completo al usuario en español, destacando los fallos detectados y las mejoras propuestas para la siguiente sesion.`

### Monitor SWING DAY — 1x/dia London open
- **Schedule:** `2 7 * * 1-5` (lunes a viernes a las 07:02 UTC)
- **Prompt:** `Ejecuta el monitor SWING de Aurex con: cd C:\Users\sagas\OneDrive\Escritorio\Documentos\BotMillonario\bot-centralizado\backend && python monitor_swing.py — luego muestra el resultado completo al usuario en español. Indica claramente si hay señal SWING y si está en MODO OBSERVACION. Si hay señal activa, menciona que el SCALP H1 quedará subordinado al SWING cuando se active en modo real.`

### Briefing semanal — Lunes apertura
- **Schedule:** `57 8 * * 1` (lunes 08:57 hora local Madrid)
- **Prompt:** `Es lunes, apertura de mercado de Londres en ~3 minutos (09:00 Madrid). Conecta al backend de Aurex en C:\Users\sagas\OneDrive\Escritorio\Documentos\BotMillonario\bot-centralizado\backend con CAPITAL_MODE=REAL. Obtén balance, posiciones abiertas, y analiza GOLD en DAY/H4/H1 con preset SWING (DAY/H4) y SCALP (H1). Genera briefing semanal de apertura en español con: 1) Estado de cuenta y posiciones, 2) Alineación multi-timeframe DAY/H4/H1 (EMAs, RSI, ATR), 3) Niveles clave de la semana (soporte/resistencia basado en BB y ATR), 4) Sesgo direccional (alcista/bajista/neutral), 5) Recomendación de acción. IMPORTANTE: Solo análisis técnico, noticias como referencia nunca como trigger.`

---

## Flujo de operación

```
Cron cada 30min (24/5)
    │
    ▼
monitor_scalp.py
    │
    ├── Muestra estado cuenta + posiciones abiertas
    │       └── Si posición > 50% hacia TP → sugiere breakeven
    │
    ├── Calcula indicadores H1 (SCALP) + H4 (SWING)
    │
    ├── ¿Hay señal en última vela completa H1?
    │       └── NO → "Sin señal - esperando" → FIN
    │
    ├── Salvaguardas (horario / H4 conflicto / duplicado / riesgo / DD)
    │       └── BLOQUEADA → informa razón → FIN
    │
    └── ABRE POSICIÓN AUTOMÁTICAMENTE
            Entry: precio actual
            SL: precio ± 0.8×ATR
            TP: precio ± 2.0×ATR
            Size: equity×1% / SL_distance
            → informa al usuario del trade abierto
```

---

## Archivos clave

| Archivo | Función |
|---------|---------|
| `monitor_scalp.py` | Monitor principal H1 — corre cada 30min, abre trades reales |
| `monitor_swing.py` | Monitor SWING DAY — observacion hasta validacion, luego real |
| `monitor_m15_obs.py` | Monitor M15 observacion — paper trading, sin dinero real |
| `session_report_daily.py` | Reporte diario de cierre — analiza P&L, fallos y mejoras |
| `strategy.py` | Presets (SCALP, SWING, SWING_CONSERVATIVE) |
| `capital_client.py` | API wrapper Capital.com |
| `backtester.py` | Backtest walk-forward con spread real |
| `bt_multi.py` | Comparativa multi-estrategia |
| `bt_rr_test.py` | Optimización R:R |
| `bt_m15.py` | Backtest M15 multi-combinacion |
| `trade_log.csv` | Registro histórico de todos los trades reales |
| `m15_signal_log.csv` | Log de señales M15 observadas (paper trading) |
| `swing_signal_log.csv` | Log de señales SWING observadas (paper trading) |
| `daily_reports/` | Reportes diarios guardados en archivo |

---

## Reglas de conducta del agente

- **Noticias = solo contexto**, nunca trigger de operación
- Si fuentes de noticias se contradicen → ignorarlas, operar solo por técnico
- Nunca abrir posición sin SL fijado en el broker
- Nunca modificar el preset SCALP sin correr backtest primero
- Informar siempre al usuario del resultado de cada revisión
- En caso de duda técnica → no operar, esperar confirmación
