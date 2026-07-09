. "$PSScriptRoot\common.ps1"

Invoke-ProjectPython -Arguments @(
    "-m", "daytrade_bot.autopilot",
    "--live",
    "--confirm-paper-orders",
    "--require-market-open",
    "--evidence-output", "data\market_scan_evidence.csv",
    "--candidates-output", "data\market_candidates.csv",
    "--failures-output", "data\market_scan_failures.csv",
    "--prices", "data\market_runtime_prices.csv",
    "--price-source", "netstock_csv",
    "--netstock-price-csv", "data\netstock_export.csv",
    "--trade-plan", "data\market_trade_plan.csv",
    "--paper-positions", "data\market_paper_positions.csv",
    "--paper-orders", "data\market_paper_orders.csv",
    "--paper-state", "data\market_paper_state.json",
    "--report", "data\market_autopilot_report.json",
    "--max-notional", "300000",
    "--max-daily-loss", "5000",
    "--max-realtime-price-age-seconds", "120",
    "--max-trades-per-day", "3",
    "--max-losing-streak", "2"
)
