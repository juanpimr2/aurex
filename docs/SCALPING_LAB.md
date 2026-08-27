# Aurex Scalping Lab

## Current Status

The scalping lab is `GO` for research and backtesting.

Live trading remains:

```text
NO_GO_FOR_REAL_TRADING
```

## Why

The current `monitor_scalp.py` is an H1 strategy with H4 confirmation. It is not
yet the high-frequency intraday scalping product target.

The new read-only lab starts testing whether a EUR 500 Capital.com CFD account
can support smaller, more frequent trades after realistic costs.

## Command

Run from `bot-centralizado/backend`:

```powershell
$env:CAPITAL_MODE='REAL'
Remove-Item Env:\AUREX_ALLOW_REAL -ErrorAction SilentlyContinue
Remove-Item Env:\AUREX_ALLOW_BROKER_MUTATION -ErrorAction SilentlyContinue
python research\scalping_lab.py --epics GOLD,US500,US100,DE40,OIL_CRUDE,OIL_BRENT,SP35 --timeframes MINUTE_5,MINUTE_15 --initial-capital 500 --risk-eur 3 --target-eur 3 --max-candles 1000 --max-trades-per-day 20 --spread-multipliers 1.0,1.5,2.0,3.0 --split-ratio 0.7 --min-trades-promote 100
```

For rolling walk-forward:

```powershell
python research\scalping_lab.py --walk-forward --wf-train-size 500 --wf-test-size 200 --wf-step-size 200 --epics GOLD,US500,US100,DE40,OIL_CRUDE,OIL_BRENT,SP35 --timeframes MINUTE_5,MINUTE_15 --initial-capital 500 --risk-eur 3 --target-eur 3 --max-candles 1000 --spread-multipliers 1.0,1.5,2.0,3.0 --min-trades-promote 100
```

The script fetches Capital.com data and never opens, modifies, or closes broker
positions.

## Walk-Forward And Cost Stress

The lab separates results into:

- `in_sample`
- `out_of_sample`

The console ranking shows out-of-sample rows first because those are more useful
for Council decisions.

The lab also runs spread stress scenarios:

- x1.0
- x1.5
- x2.0
- x3.0

Each result is classified:

- `NO_DATA`: no trades under the filters.
- `EXPLORATORY_LOW_SAMPLE`: result has fewer than the promotion threshold.
- `CANDIDATE`: enough trades, positive expectancy, PF >= 1.3, and drawdown within policy.
- `REJECTED`: enough data but insufficient risk/return.

No configuration should be promoted from fewer than 100 trades unless explicitly
marked as exploratory.

The summary ranks out-of-sample aggregates by configuration and reports how
many windows were positive. This reduces the risk of selecting a lucky single
split from many tested combinations.

## First Preliminary Run

Generated UTC: `2026-08-27 12:51:55`

Configuration:

- initial capital: EUR 500
- risk per trade: EUR 3
- target per trade: EUR 3
- spread model: observed spread x 1.5
- slippage model: 0.25 x observed spread
- max trades per day: 20
- instruments: GOLD, US500, US100, DE40, OIL_CRUDE, OIL_BRENT, SP35
- timeframes: MINUTE_5, MINUTE_15

Top preliminary results:

| Instrument | Timeframe | Session | Trades | P&L | PF | WR | Expectancy | DD |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| US500 | MINUTE_15 | London | 6 | 5.00 | 2.20 | 83.3% | 0.833 | 0.83% |
| US100 | MINUTE_15 | London | 11 | 2.23 | 1.15 | 63.6% | 0.203 | 2.15% |
| DE40 | MINUTE_15 | NY overlap | 7 | -1.38 | 0.87 | 57.1% | -0.197 | 1.70% |
| GOLD | MINUTE_15 | NY overlap | 13 | -2.86 | 0.86 | 53.8% | -0.220 | 1.11% |
| GOLD | MINUTE_15 | all | 47 | -47.27 | 0.51 | 40.4% | -1.006 | 9.97% |

Interpretation:

- GOLD does not currently pass the EUR 3 scalping hypothesis.
- US500 M15 London is interesting but has too few trades to trust.
- The target is viable only if the edge survives spread/slippage and enough
  out-of-sample data.

## Next Experiments

1. Expand historical sample beyond 1000 candles where possible.
2. Add walk-forward split and dataset hashes.
3. Add spread stress tests: x1.0, x1.5, x2.0, x3.0.
4. Add ATR-target variants instead of only fixed EUR target.
5. Add paper-trading simulator output before any supervised live mode.

## Walk-Forward Preliminary Run

Generated UTC: `2026-08-27 13:33:23`

Configuration:

- initial capital: EUR 500
- risk per trade: EUR 3
- target per trade: EUR 3
- spread stress: x1.0, x1.5, x2.0, x3.0
- slippage: 0.25 x observed spread
- split ratio: 70% in-sample, 30% out-of-sample
- promotion threshold: 100 trades

Top out-of-sample rows:

| Instrument | Timeframe | Session | Spread x | Trades | P&L | PF | WR | Expectancy | Class |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| DE40 | MINUTE_15 | NY overlap | 1.0 | 3 | 1.60 | 1.46 | 66.7% | 0.532 | EXPLORATORY_LOW_SAMPLE |
| OIL_BRENT | MINUTE_5 | all | 3.0 | 8 | 3.33 | 1.41 | 75.0% | 0.417 | EXPLORATORY_LOW_SAMPLE |
| SP35 | MINUTE_15 | London | 3.0 | 4 | 1.67 | 1.41 | 75.0% | 0.417 | EXPLORATORY_LOW_SAMPLE |
| SP35 | MINUTE_5 | NY overlap | 1.5 | 4 | 1.33 | 1.32 | 75.0% | 0.333 | EXPLORATORY_LOW_SAMPLE |

Interpretation:

- No result is currently promotable.
- Positive rows are too small to trust.
- The next useful improvement is a larger historical dataset or a paper
  forward-test stream that accumulates enough trades without broker mutations.

## Rolling Walk-Forward Run

Generated UTC: `2026-08-27 13:42:39`

Configuration:

- 168 configurations tested
- rolling windows: 500 train / 200 test / 200 step
- initial capital: EUR 500
- risk per trade: EUR 3
- target per trade: EUR 3
- spread stress: x1.0, x1.5, x2.0, x3.0
- slippage: 0.25 x observed spread
- promotion threshold: 100 trades

Outcome:

- zero `CANDIDATE` configurations
- all ranked rows are `EXPLORATORY_LOW_SAMPLE`
- best ranked aggregates still had too few trades and unstable windows

Top rows:

| Instrument | Timeframe | Session | Spread x | Trades | Windows Positive/With Trades | P&L | Avg PF | Expectancy | Class |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| OIL_BRENT | MINUTE_15 | all | 1.0 | 12 | 1/2 | -10.32 | 1.00 | -0.860 | EXPLORATORY_LOW_SAMPLE |
| DE40 | MINUTE_15 | London | 1.5 | 9 | 1/2 | -10.66 | 1.00 | -1.184 | EXPLORATORY_LOW_SAMPLE |
| DE40 | MINUTE_15 | all | 2.0 | 15 | 1/2 | -6.28 | 0.96 | -0.419 | EXPLORATORY_LOW_SAMPLE |
| SP35 | MINUTE_15 | NY overlap | 3.0 | 5 | 1/2 | 3.58 | 0.94 | 0.716 | EXPLORATORY_LOW_SAMPLE |
| GOLD | MINUTE_15 | NY overlap | 1.0 | 2 | 0/1 | -0.72 | 0.79 | -0.360 | EXPLORATORY_LOW_SAMPLE |

Council interpretation:

- The current breakout scalping hypothesis does not justify paper or live
  trading.
- GOLD remains unproven for EUR 3 scalping.
- The next useful work is either better historical data depth or a different
  hypothesis family, such as ATR-target momentum pullback, VWAP/session range,
  or opening-range breakout.
