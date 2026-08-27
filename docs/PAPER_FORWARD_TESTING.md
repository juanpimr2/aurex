# Paper Forward Testing

SPEC-009 adds the read-only bridge between historical scalping backtests and any
future supervised-live decision.

## Purpose

The paper forward-test collector records live candidate setups and resolves
their hypothetical outcomes from later candles. It is evidence gathering, not
trading.

## Safety Boundary

- No Capital.com positions are opened.
- No Capital.com positions are closed.
- No SL/TP levels are modified.
- Broker mutation gates remain unchanged.
- Paper evidence is separate from broker truth and reconciliation state.

## Module

```text
bot-centralizado/backend/research/paper_forward_collector.py
```

The module provides:

- stable candidate IDs for deduplication
- JSONL persistence for paper candidates
- deterministic TP/SL outcome resolution from OHLC candles
- aggregate summary for runtime/dashboard consumption
- a read-only live collection runner

Default store:

```text
bot-centralizado/backend/research/paper_forward_events.jsonl
```

The store is created only when candidates are explicitly written. Reading the
summary does not create files.

## Commands

Show current paper state:

```powershell
py -m research.paper_forward_collector --summary
```

Collect live paper candidates from Capital.com candles:

```powershell
py -m research.paper_forward_collector --collect-live --epics GOLD,US500,US100,DE40 --timeframes MINUTE_5,MINUTE_15
```

For REAL account data, set `CAPITAL_MODE=REAL` in the process environment.
This still does not enable broker mutations.

The runner:

- fetches candles through read-only `CapitalClient` methods
- creates a candidate only when deterministic filters pass
- deduplicates repeated polling observations
- resolves open paper candidates from later candles
- prints a compact JSON summary for Council sessions

## Runtime Contract

`/api/runtime/status` includes a `paper_forward` block:

```json
{
  "schema_version": "paper-forward.v1",
  "status": "NO_DATA",
  "total_candidates": 0,
  "open_candidates": 0,
  "closed_candidates": 0,
  "broker_mutations": "disabled"
}
```

## Promotion Logic

Paper forward testing can support a future supervised-live discussion only if:

- enough candidates are collected
- paper results agree with historical walk-forward behavior
- results remain positive after realistic costs
- runtime health and reconciliation stay green
- the Council records a written evidence-based GO decision

Until then, scalping remains research/paper only.
