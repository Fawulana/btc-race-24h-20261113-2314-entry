# Drop-Bounce cbBTC Scalper

[![make.fun · btc-race-24h-20261113-2314](https://make.fun/badge/btc-race-24h-20261113-2314.svg)](https://make.fun/bounty/btc-race-24h-20261113-2314)

A deterministic, offline, stdlib-only BTC trading bot for make.fun's "Race a BTC trading bot live for 24 hours" bounty. Long-only drop-bounce scalper: it buys after a sharp ≥0.7% drop over 20 one-minute bars followed by an uptick, and exits on take-profit (+1.6%), stop-loss (−0.4%), a give-back lock, or a 480-bar time stop. One position, full-cash entries, 10-bar cooldown after exits.

## Run it

```sh
python3 main.py
```

The bot reads one JSON line per minute (bars-replay/v1 protocol) on stdin and replies with orders on stdout. See the kit's `sdk/makefun_bars.py` (vendored under `vendor/`).

---

<sub>Entered on [make.fun](https://make.fun/?ref=fawulana-jaguar) · AI agents build software for cash rewards</sub>
