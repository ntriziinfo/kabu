param(
    [string] $InputCsv = "data\netstock_export.csv",
    [string] $OutputCsv = "data\market_runtime_prices.csv",
    [string] $SymbolsCsv = "data\symbols.csv",
    [string] $PriceColumn = ""
)

. "$PSScriptRoot\common.ps1"

$arguments = @(
    "-m", "daytrade_bot.netstock_prices",
    "--input", $InputCsv,
    "--output", $OutputCsv,
    "--symbols", $SymbolsCsv
)

if ($PriceColumn) {
    $arguments += @("--price-column", $PriceColumn)
}

Invoke-ProjectPython -Arguments $arguments
