. "$PSScriptRoot\common.ps1"

Invoke-ProjectPython -Arguments @("-m", "daytrade_bot.doctor")
Invoke-ProjectPython -Arguments @("-m", "daytrade_bot.market_calendar", "--as-of", "2026-07-09T09:05:00")
