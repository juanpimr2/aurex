# Skill: API Capital.com (capital_client.py)

> Quirks aprendidos a base de producción. Leer antes de tocar el cliente.

## Sesión
- Login por `X-CAP-API-KEY` + email/password (.env, NUNCA en git). Tokens en headers CST/X-SECURITY-TOKEN.
- Expira ~10 min inactividad → `ensure_session()` re-loguea solo.
- "Read timed out" recurrente → login lleva retry con backoff 3s/6s (no quitar). 4xx no se reintenta.

## Precios (`get_prices`)
- Ventanas móviles por TF (máx 1000 velas): DAY ~39 meses · H4 ~7.5m · H1 ~2m · **M15 ~15 días**.
- OHLC en **BID**. El spread solo se modela en backtest (0.5 pts). M15/H1 NO son backtesteables
  con la API → por eso existe `collect_candles.py` (acumulación propia diaria).

## Órdenes
- `open_position`: POST → dealReference → GET /confirms → dealId si ACCEPTED.
  **Hueco H3:** si el confirm falla tras aceptarse, devuelve None con posición viva → reconciliar por dealId.
- `modify_position`: PUT reemplaza TODO el estado → siempre preservar SL/TP no pasados (fix TP-wipe).
- SL/TP se redondean a 2 decimales.

## Historial (reconciliación — fuente de verdad)
- `get_transaction_history`: P&L realizado por cierre, con dealId. **Moneda: EUR** (la cuenta es EUR
  aunque los CSVs históricos digan "$").
- **400 si `to` ≥ ahora** → para el último tramo, omitir `to` (fix en reconcile.py, no regresionar).
- Rangos largos → trocear (~10 días por consulta). `get_activity_history` limita aún más el rango.
- SWAP = fees overnight (excluir del P&L de trades).

## Sincronización
`python reconcile.py [YYYY-MM-DD]` → tabla `trade_closes` (INSERT OR IGNORE por reference).
Correr tras cada cierre de trade o a diario. El reporting debe preferir esta tabla a los CSVs.
