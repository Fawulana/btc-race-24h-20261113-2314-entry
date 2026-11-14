# SPDX-License-Identifier: MIT
"""Drop-bounce cbBTC scalper for make.fun btc-race-24h-20261113-2314.

Strategy (long only, one position, full-size entries):
  * Entry, when flat and out of cooldown: the close fell at least 0.7% over the
    last 20 one-minute bars AND the latest close ticked up from the previous
    close. A sharp short drop followed by an uptick is where this market's
    intraday bounces start; a slow drift down never triggers it.
  * Exit, once holding, whichever comes first:
      - take profit at +1.6% of cost,
      - stop loss at -0.4% of cost,
      - give-back lock: once the position has been +0.8% or better, sell if it
        falls back to +0.4% (keep half of a real bounce, don't ride it to zero),
      - time stop after 480 bars held.
  * After any exit, a 10-bar cooldown before the next entry, so one slide is
    never re-entered bar after bar.

Risk control: at most one open position, sized at 100% of cash (the cap the
harness allows); every order caps slippage at 100 bps from the latest close,
so a fill past a gap is refused and retried next bar instead of chasing. The
worst drawdown on the dev window is ~1.5% of equity, far inside the 25% bar.

Determinism: every decision is a pure function of the bars and the account the
harness sends. No clock, no randomness, no environment, no files, no network.
All indicator state is rebuilt from the bar stream, including warm-up bars.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

SYMBOL = "CBBTC"

# --- tuned constants (grid-searched on the frozen dev window) ---
LOOKBACK_BARS = 20          # drop measured over this many bars
DROP_BPS = 70               # entry needs a >= 0.7% fall over LOOKBACK_BARS
TAKE_PROFIT_BPS = 160       # exit at +1.6% of cost
STOP_LOSS_BPS = 40          # exit at -0.4% of cost
GIVEBACK_ARM_BPS = 80       # arm the give-back lock once +0.8% is reached
GIVEBACK_KEEP_BPS = 40      # ... then sell if the gain falls back to +0.4%
MAX_HOLD_BARS = 480         # time stop, in bars held
COOLDOWN_BARS = 10          # bars to wait after an exit before re-entering
MIN_HISTORY_BARS = 90       # bars of history before the first entry is allowed
MAX_SLIPPAGE_BPS = 100      # per-order slippage cap vs the latest close

# Closes seen so far, oldest first, as integer price units (price_scale 5).
closes: list[int] = []
# Bar index (into closes) where the current position was entered, or -1.
entry_bar = -1
# Highest position value (micro-USDC) seen since entry; the give-back lock
# compares the current value against it through the cost, all in integers.
peak_value = 0
# Bar index until which entries are blocked (after an exit).
cooldown_until = -1


def on_batch(state, batch):
    global entry_bar, peak_value, cooldown_until
    for bar in batch["bars"]:
        if bar["symbol"] == SYMBOL:
            closes.append(int(bar["c"]))
    if state.warming_up:
        return []
    held = state.positions.get(SYMBOL)
    now = len(closes) - 1  # index of the latest close

    if held is not None and held.qty > 0:
        # --- holding: check exits on this close ---
        # All comparisons are exact integer ones against the position's cost,
        # so the same bars always give the same decision.
        value = state.value(SYMBOL, held.qty)
        cost = held.cost
        if value > peak_value:
            peak_value = value
        exit_now = False
        if value * 10_000 >= cost * (10_000 + TAKE_PROFIT_BPS):
            exit_now = True
        elif value * 10_000 <= cost * (10_000 - STOP_LOSS_BPS):
            exit_now = True
        elif (peak_value * 10_000 >= cost * (10_000 + GIVEBACK_ARM_BPS)
              and value * 10_000 <= cost * (10_000 + GIVEBACK_KEEP_BPS)):
            exit_now = True
        elif entry_bar >= 0 and now - entry_bar >= MAX_HOLD_BARS:
            exit_now = True
        if exit_now:
            cooldown_until = now + COOLDOWN_BARS
            entry_bar = -1
            peak_value = 0
            return [{"side": "sell", "symbol": SYMBOL, "qty": held.qty,
                     "max_slippage_bps": MAX_SLIPPAGE_BPS}]
        return []

    # --- flat: check entry ---
    if len(closes) < MIN_HISTORY_BARS or now < cooldown_until:
        return []
    if now < LOOKBACK_BARS:
        return []
    close_now = closes[now]
    close_prev = closes[now - 1]
    close_back = closes[now - LOOKBACK_BARS]
    # Sharp drop over the lookback: close_now <= close_back * (1 - 0.7%),
    # exact integer comparison, plus an uptick on the latest close.
    if (close_now * 10_000 <= close_back * (10_000 - DROP_BPS)
            and close_now > close_prev):
        entry_bar = now
        peak_value = 0
        return [{"side": "buy", "symbol": SYMBOL, "notional_quote_units": state.cash,
                 "max_slippage_bps": MAX_SLIPPAGE_BPS}]
    return []


makefun_bars.run(on_batch)
