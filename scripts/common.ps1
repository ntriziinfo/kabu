$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$BundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

function Get-ProjectPython {
    if (Test-Path $BundledPython) {
        return $BundledPython
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return $python.Source
    }

    throw "Python was not found. Install Python or run this inside the Codex workspace."
}

function Invoke-ProjectPython {
    param(
        [Parameter(Mandatory = $true)]
        [string[]] $Arguments
    )

    $python = Get-ProjectPython
    Push-Location $RepoRoot
    try {
        & $python @Arguments
    }
    finally {
        Pop-Location
    }
}
