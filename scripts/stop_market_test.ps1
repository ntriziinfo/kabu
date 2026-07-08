. "$PSScriptRoot\common.ps1"

$StopFile = Join-Path $RepoRoot "STOP_TRADING"
$Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
"stop requested at $Timestamp from stop_market_test.ps1" | Set-Content -Path $StopFile -Encoding UTF8
Write-Host "STOP_TRADING created: $StopFile"
