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
python research\scalping_lab.py --epics GOLD,US500,US100,DE40,OIL_CRUDE,OIL_BRENT,SP35 --timeframes MINUTE_5,MINUTE_15 --initial-capital 500 --risk-eur 3 --target-eur 3 --max-candles 1000 --max-trades-per-day 20
```

The script fetches Capital.com data and never opens, modifies, or closes broker
positions.

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
3. Add spread stress tests: x1.0, x1.5, x2.0.
4. Add ATR-target variants instead of only fixed EUR target.
5. Add paper-trading simulator output before any supervised live mode.
