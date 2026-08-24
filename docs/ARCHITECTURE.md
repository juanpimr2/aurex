# Aurex Architecture

## Product Shape

Aurex is evolving from a personal trading bot into a professional operations
application around a guarded trading runtime.

## Layers

- **Broker boundary:** `bot-centralizado/backend/capital_client.py`
- **Runtime guards:** `runtime_config.py`, `risk_config.py`
- **Strategy logic:** `strategy.py`
- **Monitors:** `monitor_swing.py`, `monitor_scalp.py`, `monitor_m15_obs.py`
- **Observable execution:** `run_monitor.py`
- **Read-only dashboard:** `bot-centralizado/frontend`
- **AI Council project context:** `.ai/`

## Runtime Direction

Production should flow through `run_monitor.py` and approved monitor scripts.
Legacy FastAPI trading routes are not production runtime.

The frontend is being repositioned as an operations dashboard first, not a
trading control panel.

## Safety Invariant

Evidence beats agent opinion:

1. code
2. tests
3. broker data
4. primary documentation
5. benchmarks
6. external evidence
7. agent opinion

Two agents agreeing is not proof. Claims must be tied to code, tests, data, or
documented broker state.
