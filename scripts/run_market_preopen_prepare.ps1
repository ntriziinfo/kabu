. "$PSScriptRoot\common.ps1"

Invoke-ProjectPython -Arguments @(
    "-m", "daytrade_bot.market_preopen_prepare"
)
