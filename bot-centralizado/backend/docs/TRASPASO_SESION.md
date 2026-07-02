# 🔄 Traspaso de sesión Aurex — 2026-07-02 08:40 UTC

> Documento de handoff antes de cambiar de modelo (Opus 4.8 → Fable 5).
> Estado real verificado contra logs y broker. Nada inventado.

---

## 🟢 POSICIÓN REAL ABIERTA (lo más importante)

**GOLD BUY x0.89** — abierta hoy 2026-07-02 08:28 UTC por el monitor M15 (MODO REAL)
- **Entry:** $4075.06
- **SL:** $4060.22 (−14.6 pts) → riesgo ~$13 (2% equity)
- **TP:** $4094.29 (+19.47 pts) → ganancia objetivo ~$17
- **R:R:** 1:1.33
- **Deal ID:** `00601567-0001-54c4-0000-0000912681ac`
- **Registrada en:** `m15_signal_log.csv` (última línea, estado OPEN)
- **SL/TP fijados en el broker** → sobreviven a reinicios/cambio de sesión.

**Por qué se abrió:** giro alcista confirmado en madrugada — SMC H4 pasó a **BULLISH BoS_BULL**, M15+H1+H4-ST alcistas, RSI M15 sano (54.3). Entrada limpia, no perseguida.

**Matiz honesto:** compra dentro de un **FVG BAJISTA de DAY (4044-4080)** = hay resistencia diaria por encima. Por eso el TP es ajustado (justo bajo el techo de la zona). Es un trade a favor del giro H4, NO contra el DAY (que sigue bajista, RSI DAY 27.4 sobrevendido).

**Cómo cerrará:** auto-cierre por el monitor cuando toque TP/SL, o el broker ejecuta el SL/TP directamente.

---

## ⚠️ NFP HOY — 2026-07-02 12:30 UTC (~4h)

- El dato de empleo de junio sale **HOY 12:30 UTC** (adelantado por el festivo del 4-jul).
- **BUG conocido:** `macro_context.py` calcula el NFP como "primer viernes" → muestra **03-jul, pero el real es 02-jul**. NO corregido aún (requiere aprobación; es solo informativo, la macro nunca dispara trades). Tenerlo en cuenta al leer la línea CONTEXTO MACRO de los monitores.
- Dato previo (mayo): NFP +172k, paro 4.3%.
- El BUY afronta el NFP con SL fijo → riesgo acotado a $13 pase lo que pase.

---

## 📊 Estado de cuenta (08:40 UTC)
- Equity ~**$646** · Disponible ~$452 (margen retenido por el BUY GOLD)
- **2 posiciones:** GOLD BUY (Aurex) + **NVDA BUY x1.0 (MANUAL DEL USUARIO — NO TOCAR**, no gestionar, no contabilizar)
- P&L real acumulado histórico: **+$13.36** (SWING 2/0 +$15.54 | M15 2/3 −$2.18 | SCALP 0)

---

## 🔧 Cambios recientes aplicados
- **1-jul (commit 1db0585):** SWING TP **2.5 → 3.5×ATR** (R:R 1:1.75). SL 2.0× y riesgo 5% intactos. Validado con backtest + walk-forward (3/4 tramos). Scripts: `bt_rr_swing.py`, `bt_wf_swing.py`. Documentado en `AUDITORIA_TECNICA.md` sec.7.
- Git limpio y pusheado (salvo `m15_signal_log.csv` con la línea del trade nuevo, pendiente de commit en el próximo backup, y `image.png` en raíz ajeno al proyecto).

---

## ⏰ Crons activos (session-only, 6, recreados 1-jul, expiran a 7 días)
- M15 cada 15min · SCALP cada 30min (L-V)
- SWING 09:02 · Reporte diario 23:03 · Backup+push 23:10 (L-V)
- Briefing semanal lunes 08:57
- **PENDIENTE B1:** los crons dependen de esta sesión Claude = punto único de fallo. Task Scheduler del SO sin aprobar.

---

## 📋 Reglas de conducta (para el modelo entrante — CLAUDE.md manda)
1. **100% autónomo:** el usuario NO está en el PC durante la operativa. Nunca pedir confirmación sobre cerrar/mover posiciones. Solo reportar.
2. **Noticias = solo contexto, NUNCA trigger.** Solo fuentes oficiales (federalreserve.gov, treasury.gov, bls.gov, whitehouse.gov).
3. **Cambios de estrategia/riesgo/ejecución → PARAR, explicar impacto, pedir aprobación.** Nunca modificar preset sin backtest.
4. **Nunca inventar** resultados, P&L, operaciones ni datos de mercado. Distinguir real vs backtest.
5. **NVDA es manual del usuario:** dejarla intacta, no contabilizar.
6. **Foco actual: SWING** (el usuario lo pidió). Preservación de capital primero, decisiones por reglas verificables.
7. No subir credenciales/.env a git.

---

## ▶️ Próximos pasos inmediatos
1. Seguir ejecutando los monitores por cron y reportar en español.
2. **Vigilar el trade GOLD BUY** — avisar del cierre TP ($4094.29) / SL ($4060.22).
3. Máxima atención al **NFP 12:30 UTC hoy** (volatilidad; operar solo técnico post-dato).
4. El backup diario (23:10) commiteará la línea del trade en `m15_signal_log.csv`.
