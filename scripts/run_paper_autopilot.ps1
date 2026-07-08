. "$PSScriptRoot\common.ps1"

Invoke-ProjectPython -Arguments @(
    "-m", "daytrade_bot.autopilot",
    "--demo",
    "--confirm-paper-orders"
)
