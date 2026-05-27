"""
Aurex — SMC Filters (Smart Money Concepts)
===========================================
Phase 1: informational only — output is displayed but does NOT block trades.
Phase 2 (future): active filtering once pattern reliability is validated.

Concepts implemented:
  - H4 bias via swing structure (HH/HL = bullish, LH/LL = bearish)
  - Break of Structure (BoS) and Change of Character (CHoCH)
  - Order Block (OB) detection — last opposing candle before a swing break
  - Fair Value Gap (FVG) — 3-candle imbalance zones
"""
import pandas as pd


# ── Swing detection ────────────────────────────────────────────────────────

def _find_swings(df: pd.DataFrame, lookback: int = 3):
    """
    Return lists of (index, price) for swing highs and swing lows.
    A swing high is a candle whose high is greater than the previous
    `lookback` and next `lookback` candles.
    """
    highs, lows = [], []
    n = len(df)
    for i in range(lookback, n - lookback):
        is_sh = all(df['high'].iloc[i] > df['high'].iloc[j]
                    for j in range(i - lookback, i + lookback + 1) if j != i)
        is_sl = all(df['low'].iloc[i] < df['low'].iloc[j]
                    for j in range(i - lookback, i + lookback + 1) if j != i)
        if is_sh:
            highs.append((i, float(df['high'].iloc[i])))
        if is_sl:
            lows.append((i, float(df['low'].iloc[i])))
    return highs, lows


def _h4_bias_and_event(df: pd.DataFrame):
    """
    Derive H4 market bias and last structural event from swing structure.

    Returns (bias: str, event: str)
      bias  : 'BULLISH' | 'BEARISH' | 'NEUTRAL'
      event : 'BoS_BULL' | 'BoS_BEAR' | 'CHoCH_BULL' | 'CHoCH_BEAR' | ''
    """
    if df is None or len(df) < 20:
        return 'NEUTRAL', ''

    highs, lows = _find_swings(df, lookback=3)
    if len(highs) < 2 or len(lows) < 2:
        return 'NEUTRAL', ''

    # Last two swing highs and lows
    sh1_idx, sh1 = highs[-2]
    sh2_idx, sh2 = highs[-1]
    sl1_idx, sl1 = lows[-2]
    sl2_idx, sl2 = lows[-1]

    hh = sh2 > sh1   # Higher High
    hl = sl2 > sl1   # Higher Low
    lh = sh2 < sh1   # Lower High
    ll = sl2 < sl1   # Lower Low

    # Determine bias
    if hh and hl:
        bias = 'BULLISH'
    elif lh and ll:
        bias = 'BEARISH'
    else:
        bias = 'NEUTRAL'

    # Determine last event — check if recent price broke a swing level
    last_close = float(df['close'].iloc[-1])
    event = ''

    # BoS bullish: price broke above previous swing high
    if last_close > sh1 and sh2_idx > sh1_idx:
        if bias == 'BULLISH':
            event = 'BoS_BULL'
        else:
            event = 'CHoCH_BULL'

    # BoS bearish: price broke below previous swing low
    elif last_close < sl1 and sl2_idx > sl1_idx:
        if bias == 'BEARISH':
            event = 'BoS_BEAR'
        else:
            event = 'CHoCH_BEAR'

    return bias, event


# ── Order Block detection ──────────────────────────────────────────────────

def _find_order_blocks(df: pd.DataFrame, highs, lows):
    """
    An Order Block (OB) is the last bearish candle before a bullish swing break
    (bullish OB) or the last bullish candle before a bearish swing break (bearish OB).

    Returns list of dicts: {type: 'BULL'|'BEAR', high: float, low: float, idx: int}
    """
    obs = []
    if len(highs) < 1 or len(lows) < 1:
        return obs

    # Bullish OB: the last bearish (red) candle before the most recent swing high
    sh_idx, sh_price = highs[-1]
    for i in range(sh_idx - 1, max(0, sh_idx - 8), -1):
        o = float(df['open'].iloc[i])
        c = float(df['close'].iloc[i])
        if o > c:  # bearish candle = potential bullish OB
            obs.append({
                'type': 'BULL',
                'high': float(df['high'].iloc[i]),
                'low':  float(df['low'].iloc[i]),
                'idx':  i,
            })
            break

    # Bearish OB: the last bullish (green) candle before the most recent swing low
    sl_idx, sl_price = lows[-1]
    for i in range(sl_idx - 1, max(0, sl_idx - 8), -1):
        o = float(df['open'].iloc[i])
        c = float(df['close'].iloc[i])
        if c > o:  # bullish candle = potential bearish OB
            obs.append({
                'type': 'BEAR',
                'high': float(df['high'].iloc[i]),
                'low':  float(df['low'].iloc[i]),
                'idx':  i,
            })
            break

    return obs


# ── Fair Value Gap detection ───────────────────────────────────────────────

def _find_fvgs(df: pd.DataFrame, lookback: int = 20):
    """
    A bullish FVG exists when candle[i-1].high < candle[i+1].low (gap up).
    A bearish FVG exists when candle[i-1].low > candle[i+1].high (gap down).

    Returns list of recent unfilled FVGs:
      {type: 'BULL'|'BEAR', top: float, bottom: float, idx: int}
    """
    fvgs = []
    start = max(1, len(df) - lookback - 1)
    for i in range(start, len(df) - 1):
        h_prev = float(df['high'].iloc[i - 1])
        l_prev = float(df['low'].iloc[i - 1])
        h_next = float(df['high'].iloc[i + 1])
        l_next = float(df['low'].iloc[i + 1])

        # Bullish FVG: gap between prev high and next low
        if l_next > h_prev:
            fvgs.append({'type': 'BULL', 'top': l_next, 'bottom': h_prev, 'idx': i})

        # Bearish FVG: gap between prev low and next high
        elif h_next < l_prev:
            fvgs.append({'type': 'BEAR', 'top': l_prev, 'bottom': h_next, 'idx': i})

    return fvgs[-3:] if fvgs else []  # Keep only the 3 most recent


# ── Public API ─────────────────────────────────────────────────────────────

def smc_summary(
    df_h4:      pd.DataFrame,
    df_m15:     pd.DataFrame = None,
    entry:      float = 0.0,
    signal:     str = None,
) -> dict:
    """
    Main entry point called from monitors.

    Always returns:
      h4_bias     : 'BULLISH' | 'BEARISH' | 'NEUTRAL'
      h4_event    : 'BoS_BULL' | 'BoS_BEAR' | 'CHoCH_BULL' | 'CHoCH_BEAR' | ''
      ob_warning  : bool — True if entry is inside an OB opposing the signal
      fvg_confluence : bool — True if entry is inside an FVG aligned with signal
    """
    result = {
        'h4_bias':        'N/A',
        'h4_event':       '',
        'ob_warning':     False,
        'fvg_confluence': False,
    }

    try:
        if df_h4 is None or len(df_h4) < 15:
            return result

        bias, event = _h4_bias_and_event(df_h4)
        result['h4_bias']  = bias
        result['h4_event'] = event

        if signal is None or entry == 0.0:
            return result

        highs, lows = _find_swings(df_h4, lookback=3)
        obs  = _find_order_blocks(df_h4, highs, lows)
        fvgs = _find_fvgs(df_h4, lookback=30)

        # OB warning: entry inside an OB that contradicts signal
        for ob in obs:
            if ob['low'] <= entry <= ob['high']:
                # Bullish OB contradicts SELL; bearish OB contradicts BUY
                if (ob['type'] == 'BULL' and signal == 'SELL') or \
                   (ob['type'] == 'BEAR' and signal == 'BUY'):
                    result['ob_warning'] = True
                    break

        # FVG confluence: entry inside an FVG aligned with signal
        for fvg in fvgs:
            if fvg['bottom'] <= entry <= fvg['top']:
                if (fvg['type'] == 'BULL' and signal == 'BUY') or \
                   (fvg['type'] == 'BEAR' and signal == 'SELL'):
                    result['fvg_confluence'] = True
                    break

    except Exception:
        pass

    return result
