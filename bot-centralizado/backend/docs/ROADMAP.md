# AUREX — ROADMAP OFICIAL
> Actualizado: 17 Apr 2026 | Capital: $246.28 | Sistema: 3 niveles

---

## VISION GENERAL

```
$246  ──────────────────────────────────────────────────────► $10,000+
 Apr    May    Jun    Jul    Ago    Sep    Oct    Nov    Dic    2027+
  │      │      │      │      │      │      │      │      │
  │   ~$280  ~$316  ~$357  ~$403  ~$455  ~$514  ~$581  ~$657
  │
  └─ Crecimiento por compounding al 13%/mes (objetivo conservador)
```

---

## FASE 1 — FUNDACION (Apr - May 2026)
**Objetivo: Estabilizar el sistema. Recuperar las perdidas. Primeras ganancias.**

```
[COMPLETADO]
  ✅ Sistema SCALP H1 operativo con trades reales
  ✅ 7 salvaguardas de riesgo implementadas
  ✅ Reporte diario automatico (23:03)
  ✅ Monitor M15 observacion
  ✅ Monitor SWING DAY observacion
  ✅ Sistema de 3 niveles construido

[EN PROGRESO — Apr 2026]
  🔄 Validando SWING DAY en observacion (→ real ~1 May)
  🔄 Acumulando datos M15 (→ real ~May-Jun)
  🔄 Recuperar -$3.72 y terminar April en positivo

[OBJETIVOS FASE 1]
  → Balance objetivo fin de Abril : $248 - $255  (+0.7% a +3.5%)
  → Balance objetivo fin de Mayo  : $265 - $280  (+7% a +13% sobre $246)
  → Activar SWING real en Mayo si validacion OK
  → WR acumulado > 30% (hoy 16.7% — solo 6 trades, muestra pequena)
```

---

## FASE 2 — CRECIMIENTO (Jun - Sep 2026)
**Objetivo: Sistema completo operativo. Compounding consistente.**

```
[HITOS CLAVE]
  Jun  → Activar M15 con dinero real si datos lo justifican
  Jun  → Balance objetivo: ~$316 (+28% desde hoy)
  Jul  → SCALP + SWING + M15 los tres operando coordinados
  Sep  → Balance objetivo: ~$455 (+85% desde hoy)

[METRICAS OBJETIVO]
  → WR consolidado : 40-45%
  → PF mensual     : > 1.5
  → MaxDD mensual  : < 8%
  → Trades/mes     : 20-40 (SCALP) + 2-5 (SWING) + 40-80 (M15)
```

---

## FASE 3 — ESCALA (Oct 2026 - 2027)
**Objetivo: Retiros parciales. Sistema autonomo demostrado.**

```
[HITOS]
  Oct  → Balance ~$514 — considerar primer retiro parcial
  Dic  → Balance ~$657 — sistema completamente autonomo
  2027 → Balance > $1,000 — posibilidad de anadir capital externo
         (cuando el sistema haya demostrado +12 meses de rentabilidad)

[CUANDO CONSIDERAR ANADIR CAPITAL]
  Solo si se cumplen TODOS:
    ✓ 6+ meses consecutivos con WR > 35%
    ✓ PF > 1.5 sostenido
    ✓ MaxDD nunca supero -15% en un mes
    ✓ Sistema ha operado sin intervencion manual
```

---

## ESTIMACION RESTO DE ABRIL (17-30 Apr 2026)

```
Dias de mercado restantes  : ~10 dias (L-V)
Trades esperados (SCALP)   : 8 - 20
  (mercado lateral = menos señales; tendencia = mas)

Escenario CONSERVADOR (WR 35%, PF 1.5):
  Ganancia estimada: +$5 a +$8
  Balance fin April: ~$251 - $254
  Resultado mes    : -$0 a +$1.7 (recuperar perdidas = exito en mes 1)

Escenario BASE (WR 43%, PF 1.72):
  Ganancia estimada: +$8 a +$15
  Balance fin April: ~$254 - $261
  Resultado mes    : +$4 a +$11 (+1.6% a +4.5%)

Escenario OPTIMO (tendencia fuerte GOLD):
  Ganancia estimada: +$15 a +$25
  Balance fin April: ~$261 - $271
  Resultado mes    : +$11 a +$21 (+4.5% a +8.5%)

NOTA: El SWING en observacion no genera dinero aun.
El M15 tampoco. Todo el P&L de Abril viene de SCALP H1.
```

---

## CATALOGO DE RIESGOS

| Riesgo | Probabilidad | Impacto | Mitigacion |
|--------|-------------|---------|-----------|
| Racha de SL (5 consecutivos) | Media | Alto | Stop diario -5%, cooling-off |
| Mercado lateral prolongado | Alta | Bajo | SWING captura tendencias largas |
| Error API Capital.com | Baja | Medio | Login retry automatico |
| Drawdown > 15% en un mes | Baja | Alto | Pausa manual, revisar estrategia |
| GOLD gap de apertura lunes | Media | Medio | Sin trades viernes 17:00+ |

---

## REGLAS DE ORO (no negociables)

1. **Nunca mover el SL** una vez colocado — ni para ampliar ni para cerrar antes
2. **Nunca añadir a una posicion perdedora** — cada trade es independiente
3. **No cambiar el preset SCALP sin backtest** — los parametros estan optimizados
4. **Respetar el stop diario** — si el bot para, es por algo
5. **Paciencia** — un mes malo no invalida una estrategia buena

---

## PROXIMAS MEJORAS TECNICAS PLANIFICADAS

| Mejora | Prioridad | Estado | ETA |
|--------|-----------|--------|-----|
| Filtro volatilidad ATR en SCALP (del Pine Script 449%) | Media | Pendiente | May 2026 |
| Activar SWING con dinero real | Alta | Observacion | ~1 May 2026 |
| Activar M15 con dinero real | Media | Observacion | ~Jun 2026 |
| Trailing stop automatico al 50% TP | Media | Pendiente | May 2026 |
| Dashboard HTML con graficos | Baja | Pendiente | Jun 2026 |
| Notificacion Telegram en trade abierto | Baja | Pendiente | Jun 2026 |
