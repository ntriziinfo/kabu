# kabu

Paper-first intraday auto-trading system for Japanese equities.

This repository starts with a paper-trading bot and a local NetStock High Speed
integration boundary.

It does not place real orders. The live order adapter is intentionally a stub so
that strategy, risk controls, logs, and paper execution can be tested before any
broker integration is attached.

## Run

```powershell
python -m daytrade_bot.main --ticks data/sample_ticks.csv --mode paper
```

In this Codex workspace, use the bundled Python if `python` is not on PATH:

```powershell
C:\Users\nitro\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m daytrade_bot.main --ticks data/sample_ticks.csv --mode paper
```

To check the installed NetStock High Speed path:

```powershell
C:\Users\nitro\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m daytrade_bot.netstock_status
```

To run a paper backtest summary:

```powershell
C:\Users\nitro\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m daytrade_bot.backtest --ticks data/sample_ticks.csv
```

To require evidence confirmation in the paper backtest:

```powershell
C:\Users\nitro\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m daytrade_bot.backtest --ticks data/sample_ticks.csv --evidence data/sample_evidence.csv
```

To score news/disclosure evidence:

```powershell
C:\Users\nitro\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m daytrade_bot.evidence_backtest --ticks data/sample_ticks.csv --evidence data/sample_evidence.csv
```

To collect Yahoo Finance Japan news into an evidence CSV:

```powershell
C:\Users\nitro\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m daytrade_bot.yahoo_finance --symbol 7203 --output data/yahoo_evidence.csv
```

To test the parser without network access:

```powershell
C:\Users\nitro\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m daytrade_bot.yahoo_finance --symbol 7203 --html-file data/sample_yahoo_finance_7203.html --output data/yahoo_evidence.csv
```

For historical tests, pin the fetch timestamp:

```powershell
C:\Users\nitro\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m daytrade_bot.yahoo_finance --symbol 7203 --html-file data/sample_yahoo_finance_7203.html --fetched-at 2026-07-08T09:12:00 --overwrite --output data/yahoo_evidence.csv
```

To open the local dashboard:

```powershell
C:\Users\nitro\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m daytrade_bot.dashboard
```

To scan a symbol list and create ranked evidence candidates:

```powershell
C:\Users\nitro\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m daytrade_bot.scanner --symbols data/symbols.csv --demo --fetched-at 2026-07-08T09:12:00
```

To scan live Yahoo Finance pages, omit `--demo`. The scanner retries failures,
waits between requests, deduplicates headlines, and writes fetch errors to
`data/scan_failures.csv`:

```powershell
C:\Users\nitro\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m daytrade_bot.scanner --symbols data/symbols.csv --delay 1.5 --retries 2
```

## Structure

- `daytrade_bot/market.py` reads tick data.
- `daytrade_bot/strategy.py` creates buy/sell signals.
- `daytrade_bot/backtest.py` runs paper mode and summarizes closed trades.
- `daytrade_bot/evidence.py` scores disclosure/news/social evidence.
- `daytrade_bot/evidence_backtest.py` replays evidence against market ticks.
- `daytrade_bot/yahoo_finance.py` collects Yahoo Finance Japan news into evidence CSV.
- `daytrade_bot/scanner.py` scans a symbol list and writes ranked candidates.
- `daytrade_bot/dashboard.py` serves a local browser dashboard.
- `daytrade_bot/risk.py` blocks unsafe orders.
- `daytrade_bot/broker.py` contains paper and live broker adapters.
- `daytrade_bot/netstock_highspeed.py` stores the local NetStock High Speed integration point.
- `daytrade_bot/netstock_broker.py` is the future live-order adapter boundary.
- `daytrade_bot/main.py` wires everything together.

## Safety Defaults

- Paper mode only by default.
- Max position size.
- Max daily loss.
- Max trades per day.
- Entry cutoff before market close.
- Emergency stop file support.

## Default Strategy

The default logic is a long-only intraday opening-range breakout:

- Build the opening range until 09:15.
- Buy only when price breaks above the opening high, trades above VWAP, and volume is stronger than recent average.
- Exit by take profit, stop loss, trailing stop, or forced end-of-day close.
- Take at most one entry per symbol per session in this starter.

## Evidence-Driven Trading

The evidence layer can ingest items from TDnet, EDINET, news APIs, social
feeds, or manual CSV files and produce a scored signal. When `--evidence` is
provided, buy orders require both a market signal and a positive evidence signal.
Negative evidence can trigger an exit while a position is open.

Default scoring favors official disclosures over social sources. Live trading
should require both a market signal and an evidence signal, plus risk checks.

Create `STOP_TRADING` in the project directory to stop the bot on the next tick.

## NetStock High Speed

The project references the installed app instead of copying proprietary files.

```text
C:\Program Files (x86)\NetStockHighSpeed\Module\HighSpeed.exe
```

The local config is `config/netstock_highspeed.json`. Live trading is locked with
`"live_trading_enabled": false` until the order window, confirmation flow, and
emergency stop behavior are mapped and tested.
