. "$PSScriptRoot\common.ps1"

Invoke-ProjectPython -Arguments @(
    "-m", "daytrade_bot.market_test_runner",
    "--interval", "300",
    "--wait-interval", "30",
    "--max-cycles", "90"
)
