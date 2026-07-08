# kabu

Paper-first intraday auto-trading system for Japanese equities.

## 現在できること

このプロジェクトは、まず安全な紙トレード用として作っています。実注文はまだ出しません。

- Yahooファイナンスのニュース材料を取得します。
- Yahooファイナンスから株価を更新します。
- 材料の強弱を点数化します。
- 銘柄ごとに買い・売り・見送り候補を作ります。
- 候補から紙トレード用の注文案を作ります。
- 注文案には株数、概算金額、損切り価格、利確価格、想定損失を出します。
- 紙トレードとして、確認後に仮想約定・保有・履歴へ反映します。
- 日次損失上限、1日の取引回数上限、連敗停止で紙トレードを止めます。
- ダッシュボードは `http://127.0.0.1:8765/` で確認できます。

実注文はまだ出しません。NetStock High Speed連携は場所の確認までで、発注は安全のためロックしています。

## ダッシュボード操作

基本の流れ:

1. `候補スキャン` でYahoo材料から売買候補を作ります。
2. `株価更新` で注文案に使う株価を更新します。
3. `注文案作成` で株数、損切り、利確、想定損失を出します。
4. 内容を見て問題なければ `紙注文を確認` を押します。
5. `紙トレード実行` で紙約定と保有履歴へ反映します。

監視設定では、最低材料点、1銘柄上限、損切り%、利確%、日次損失上限、1日取引上限、連敗停止を変更できます。
`紙自動処理` がONの場合、監視中に株価更新、候補スキャン、注文案作成、紙トレード処理まで自動で回します。
新規買いは `実行前確認` がONなら、`紙注文を確認` を押すまで待ちます。保有中の損切り/利確判定は紙トレード上で自動処理されます。
初期サンプル価格は `data/latest_prices.csv`、実行時の更新価格は `data/runtime_prices.csv` に保存されます。

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

To run the automated tests:

```powershell
C:\Users\nitro\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest discover -s tests
```

Shortcut scripts are also available:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_dashboard.ps1
powershell -ExecutionPolicy Bypass -File scripts\run_tests.ps1
powershell -ExecutionPolicy Bypass -File scripts\run_demo_cycle.ps1
powershell -ExecutionPolicy Bypass -File scripts\doctor.ps1
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

To run repeated monitoring from the command line:

```powershell
C:\Users\nitro\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m daytrade_bot.monitor --symbols data/symbols.csv --demo --interval 60
```

The dashboard also has `Start monitor` and `Stop monitor` buttons. Monitoring
updates candidates and writes status to `data/monitor_status.json`. The
dashboard settings panel controls demo/live mode, scan interval, request delay,
retry count, and timeout. Real orders are still disabled.

To build a paper trade plan from ranked candidates:

```powershell
C:\Users\nitro\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m daytrade_bot.trade_plan --candidates data/candidates.csv --prices data/latest_prices.csv
```

The trade plan uses a minimum evidence score, max notional, 100-share lot size,
stop-loss percent, and take-profit percent to decide whether a candidate is
ready for paper execution. It does not send real orders.

## Structure

- `daytrade_bot/market.py` reads tick data.
- `daytrade_bot/strategy.py` creates buy/sell signals.
- `daytrade_bot/backtest.py` runs paper mode and summarizes closed trades.
- `daytrade_bot/evidence.py` scores disclosure/news/social evidence.
- `daytrade_bot/evidence_backtest.py` replays evidence against market ticks.
- `daytrade_bot/yahoo_finance.py` collects Yahoo Finance Japan news into evidence CSV.
- `daytrade_bot/yahoo_prices.py` updates quote prices from Yahoo Finance Japan.
- `daytrade_bot/scanner.py` scans a symbol list and writes ranked candidates.
- `daytrade_bot/monitor.py` repeats candidate scans and writes monitor status.
- `daytrade_bot/health.py` summarizes warnings for dashboard operation.
- `daytrade_bot/doctor.py` runs local diagnostics across the paper trading system.
- `daytrade_bot/trade_plan.py` converts ranked candidates into paper order candidates.
- `daytrade_bot/paper_execution.py` executes guarded paper orders.
- `daytrade_bot/paper_summary.py` summarizes paper positions, risk, and PnL.
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
