# Aurex Live Trading Policy

## Current Verdict

`NO_GO_FOR_REAL_TRADING`

Aurex may supervise, analyze, backtest, reconcile, and display broker state. It
must not submit broker mutations until a supervised live session is explicitly
approved and the required gates are ready.

## Objective

The near-term business objective is to test whether Aurex can grow a EUR 500
account toward a EUR 550 weekly target.

This is not a guarantee. It is a product objective to measure against risk,
execution quality, and drawdown.

## V1 Supervised Policy

- Allowed instrument: `GOLD`.
- Max open positions: `1`.
- Max risk per trade: `1%`.
- Max daily loss: `EUR 10`.
- Max weekly loss: `EUR 25`.
- Stop loss is required.
- Take profit is required.
- Broker/local reconciliation must be OK.
- Runtime health must be green.
- Dashboard remains read-only.

## Required Readiness Gates

These are reported by the runtime `live_policy` contract:

- `AUREX_LIVE_POLICY_ACCEPTED=YES`
- `AUREX_LIVE_SESSION_APPROVED=YES`
- `AUREX_KILL_SWITCH_READY=YES`
- all open positions must be inside policy scope
- account must have capacity under the max open positions limit
- visible positions must include stop loss and take profit
- pending broker working orders must be reviewed first

Even when those are ready, broker mutation still requires the existing runtime
safety gates:

- `CAPITAL_MODE=REAL`
- `AUREX_ALLOW_REAL=YES`
- `AUREX_ALLOW_BROKER_MUTATION=YES`

Strategy-specific gates may also apply.

## Council Operating Rule

Codex Council may act as orchestrator and reviewer. Claude/Codex agents may
analyze, implement, and review. Agent consensus is not enough to approve live
trading.

Evidence priority:

1. code
2. tests
3. broker/runtime data
4. primary documentation
5. benchmarks
6. external evidence
7. agent opinion
