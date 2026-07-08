. "$PSScriptRoot\common.ps1"

Invoke-ProjectPython -Arguments @(
    "-m", "daytrade_bot.monitor",
    "--symbols", "data\symbols.csv",
    "--demo",
    "--fetched-at", "2026-07-08T09:12:00",
    "--once",
    "--interval", "1",
    "--evidence-output", "data\scan_evidence.csv",
    "--candidates-output", "data\candidates.csv",
    "--failures-output", "data\scan_failures.csv",
    "--prices", "data\runtime_prices.csv",
    "--demo-prices", "data\latest_prices.csv",
    "--trade-plan-output", "data\trade_plan.csv",
    "--update-prices",
    "--paper-execute"
)
