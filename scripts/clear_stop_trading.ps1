. "$PSScriptRoot\common.ps1"

$StopFile = Join-Path $RepoRoot "STOP_TRADING"
if (Test-Path $StopFile) {
    Remove-Item -LiteralPath $StopFile
    Write-Host "STOP_TRADING removed: $StopFile"
} else {
    Write-Host "STOP_TRADING was not present."
}
