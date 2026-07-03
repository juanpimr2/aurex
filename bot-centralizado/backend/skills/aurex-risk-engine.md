# Skill: Motor de riesgo de Aurex

> Reglas que protegen el dinero. Cambiarlas requiere validación cuantitativa + OK del usuario.

## Sizing (strategy.get_position_size)
`size = equity × riesgo% / distancia_SL` · mínimo broker 0.01.
Riesgo por nivel: **SWING 5% · M15 2% · SCALP 1%** (SWING 5% = decisión explícita del usuario).

## SL/TP (siempre en el broker, nunca en memoria)
- SWING: SL 2.0×ATR / TP **3.5×ATR** (aprobado 1-jul-2026, R:R 1:1.75)
- SCALP: SL 0.8× / TP 2.0× · M15: SL 1.5× / TP 2.0×
- Regla de oro: **jamás posición sin SL+TP fijados en Capital.com** (sobreviven a caídas del PC).
- PUT /positions REEMPLAZA el estado completo → `modify_position` preserva el nivel no pasado
  (bug TP-wipe, corregido — no regresionar).

## Salvaguardas (bloquean señales; orden en monitor_scalp.py)
1. Viernes ≥17:00 Madrid → no abrir (cierre semanal)
2. Conflicto H4 → no operar contra el marco superior
3. Anti-duplicado: no repetir dirección en GOLD
4. Riesgo abierto máx 5% equity (nota H2: cuenta posiciones externas — impreciso pero conservador)
5. Pausa si PnL abierto < −10% equity
6. Stop diario: P&L día < −5% → parar
7. Cooling-off tras SL (RSI 35-65 + EMAs alineadas para reentrar)
8. Filtros de volatilidad: SCALP ATR>1.2×SMA20 · M15 ATR>SMA50 + anti-spike (ATR>2.5×SMA50 → fuera)
9. Noticias = SOLO contexto. Jamás trigger (macro_context.py; bug conocido: NFP asume 1er viernes)

## Números de referencia (verdad del broker, jul-2026)
57 trades · WR ~51% · PF ~1.85 · avg win ~+6€ / avg loss ~−3.4€ · MaxDD backtest 5%: **23%** a 39 meses.
La mitad de los trades pierden POR DISEÑO — la asimetría win/loss hace la rentabilidad.

## Kill switch (condiciones que justifican parar todo)
Órdenes duplicadas · posición sin SL en broker · exposición > configurada · datos corruptos/stale
· divergencia broker↔logs sin explicación · fallos de API en cadena. Ante cualquiera: no abrir
nuevas posiciones, documentar causa exacta, avisar al usuario con plan de recuperación.
