# Aurex Council Operating Plan

Date: 2026-08-27

This document records how the AI Council should operate Aurex as a professional
product/repository without bypassing trading safety controls.

## Current State

- Global Council lives at `C:\Users\sagas\.ai-council`.
- Aurex-specific Council context lives under project `.ai/`.
- Dashboard/runtime is available at `http://127.0.0.1:8181/`.
- Runtime status endpoint is read-only: `/api/runtime/status`.
- Capital.com connection is working in REAL mode, but broker mutations are
  blocked unless the explicit safety gates are enabled.
- Latest Council runtime snapshot showed:
  - balance: 500.62 EUR
  - open positions: 0
  - working orders: 0
  - reconciliation: ok
  - live verdict: `NO_GO_FOR_REAL_TRADING`

## Non-Negotiable Safety Rules

- The Council may read broker state, prices, logs, runtime status, tests, and
  repository evidence.
- The Council must not open, close, or modify broker positions during research,
  audit, or dashboard work.
- A profitable backtest is not enough for live trading.
- Two agents agreeing is not proof. Decisions require evidence from code,
  tests, data, primary documentation, and runtime behavior.
- Claude/Codex provider failures must be documented. A missing agent verdict
  must not be invented.

## Default SDD Flow

Important changes follow this flow:

```text
request -> discovery -> spec -> architecture -> implementation plan
-> implementation -> review -> tests -> evaluation -> documentation
```

Small fixes may compress the flow, but must still record scope, evidence,
verification, and residual risk.

## Council Roles

Codex Council:

- owns orchestration, planning, implementation integration, review, and final
  client verdict
- keeps repo state professional: issues, branches, PRs, checks, docs
- blocks unsafe trading actions

Claude Agent:

- acts as strategy researcher, product critic, architecture reviewer, or
  developer advisor when available
- must receive a fresh sanitized Capital/Aurex snapshot for trading-related
  prompts
- timeout or unavailability is a provider degradation, not a reason to stop the
  Council

Additional Codex agents:

- can review strategy evidence, tests, dashboard UX, backend contracts, or PRs
- should produce bounded verdicts, not duplicate the orchestrator

## Scalping Evidence So Far

SPEC-008 added train/test, rolling walk-forward, spread stress, and
out-of-sample classification for the scalping lab.

Current conclusion:

- GOLD is not approved for live scalping.
- No configuration has enough out-of-sample evidence to become a live candidate.
- Some instruments are worth continued research, but only through paper/lab
  evidence first.

## Next PR Plan

### SPEC-009: Paper Forward-Test Collector

Status: in progress

Goal:

- Record live read-only signals and hypothetical fills without broker mutation.
- Persist every candidate setup, filter decision, spread estimate, SL/TP model,
  and outcome.
- Build an evidence bridge between historical backtests and supervised live
  trading.

Acceptance criteria:

- no broker mutation code paths are added or enabled
- collector can run repeatedly without duplicating events
- results are visible from docs or dashboard
- tests cover deduplication, outcome accounting, and safety gates

### SPEC-010: Dashboard Council View

Goal:

- Add a client-facing view that separates account state, runtime safety,
  signals, backtest evidence, and Council verdicts.

Acceptance criteria:

- dashboard clearly says when Aurex is read-only
- live broker state cannot be confused with simulated/paper results
- no buttons or endpoints submit broker mutations
- browser/build verification passes

### SPEC-011: Provider Health

Goal:

- Make Codex/Claude provider availability visible in Council session reports.

Acceptance criteria:

- Claude timeout/unavailability is captured as a first-class event
- prompts include runtime snapshots for trading tasks
- fallback provider behavior is documented

## Promotion Gates

Paper trading can be considered only when:

- runtime health and reconciliation are green
- at least one strategy has sufficient out-of-sample sample size
- results survive realistic spread/slippage stress
- paper forward-test agrees with historical backtest behavior

Supervised live trading can be considered only after:

- explicit user approval for a bounded session
- kill switch is available and tested
- max loss and max open position controls are enforced
- SL and TP are mandatory
- Council produces a written GO decision with evidence

Autonomous live trading is out of scope for the current platform stage.
