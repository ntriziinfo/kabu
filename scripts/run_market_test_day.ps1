param(
    [switch] $SkipPreopen,
    [switch] $SkipReadyCheck,
    [switch] $PrepareOnly,
    [int] $IntervalSeconds = 300,
    [int] $WaitIntervalSeconds = 30,
    [int] $MaxCycles = 90
)

. "$PSScriptRoot\common.ps1"

function Invoke-MarketTestStep {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name,
        [Parameter(Mandatory = $true)]
        [string[]] $Arguments
    )

    Write-Host ""
    Write-Host "== $Name =="
    Invoke-ProjectPython -Arguments $Arguments
}

if (-not $SkipPreopen) {
    Invoke-MarketTestStep -Name "1/3 Pre-open prepare: update Yahoo evidence, prices, and trade plan" -Arguments @(
        "-m", "daytrade_bot.market_preopen_prepare"
    )
}

if ($PrepareOnly) {
    Write-Host ""
    Write-Host "Pre-open preparation finished. No live orders or paper orders were submitted."
    exit 0
}

if (-not $SkipReadyCheck) {
    Invoke-MarketTestStep -Name "2/3 System doctor" -Arguments @(
        "-m", "daytrade_bot.doctor"
    )
    Invoke-MarketTestStep -Name "2/3 Market calendar check" -Arguments @(
        "-m", "daytrade_bot.market_calendar"
    )
}

Invoke-MarketTestStep -Name "3/3 Paper market session: wait for the JPX session, then run" -Arguments @(
    "-m", "daytrade_bot.market_test_runner",
    "--interval", "$IntervalSeconds",
    "--wait-interval", "$WaitIntervalSeconds",
    "--max-cycles", "$MaxCycles"
)
