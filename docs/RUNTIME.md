# Aurex Runtime

## Current Verdict

Real trading is `NO-GO` until tests, broker reconciliation, and explicit Council
approval are complete.

The current safe mode is read-only supervision plus guarded monitor execution.

## Production Entry Point

Approved runtime wrapper:

```bash
cd bot-centralizado/backend
python run_monitor.py monitor_swing.py
python run_monitor.py monitor_scalp.py
python run_monitor.py monitor_m15_obs.py
```

The wrapper records process start, duration, exit code, and notable trade/error
strings.

## Broker Mutation Gate

`CapitalClient` is the broker boundary. These methods are treated as mutations:

- `open_position`
- `modify_position`
- `close_position`

In `REAL`, mutation requires all of:

```text
CAPITAL_MODE=REAL
AUREX_ALLOW_REAL=YES
AUREX_ALLOW_BROKER_MUTATION=YES
```

Strategy-specific gates may also apply:

```text
AUREX_ALLOW_SCALP_REAL=YES
AUREX_ALLOW_M15_REAL=YES
```

M15 remains observation-only unless a future spec explicitly promotes it.

## Legacy Runtime

Legacy runtime is disabled by default:

- `bot-centralizado/backend/legacy/main.py`
- `bot-centralizado/backend/legacy/trader.py`
- `bot-centralizado/backend/legacy/open_trade.py`

It requires:

```text
AUREX_ALLOW_LEGACY_RUNTIME=YES
```

That flag is for isolated lab work only, not production.

## Dashboard

The Vue dashboard is read-only. It may display:

- account state
- open positions
- Council verdict
- runtime gates
- strategy cards
- event timeline

It must not provide buttons that open, close, modify, start, or stop live
trading.

CI enforces this boundary with:

```bash
python tools/check_readonly_contract.py
```

The check allows the backtest endpoint, but rejects live-trading mutation
requests from the Vue dashboard and rejects broker mutation calls outside the
approved guarded runtime modules.

## Runtime Status Contract

Canonical read-only runtime endpoint:

```text
GET /api/runtime/status
```

The endpoint reports:

- schema version
- broker mode and read-only status
- real-trading verdict
- account and positions snapshot, when available
- broker/local reconciliation summary
- runtime gates
- monitor health
- stable errors

It must not call:

- `open_position`
- `modify_position`
- `close_position`

The endpoint may report that broker mutation gates are enabled in the local
environment, but the dashboard mutation surface itself must remain disabled.

## Broker/Local Reconciliation

The runtime status includes a read-only `reconciliation` section. It compares
broker positions already fetched by the dashboard with local CSV rows that still
claim an `OPEN` or `PENDIENTE` trade.

If local logs claim an open/pending trade but the broker has no matching
position, the status becomes:

```text
stale_local_state
```

That condition blocks any real-trading approval until reviewed. It does not
mean a broker position is currently open; it means local state is not clean
enough to trust for autonomous execution.
