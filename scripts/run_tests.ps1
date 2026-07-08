. "$PSScriptRoot\common.ps1"

Invoke-ProjectPython -Arguments @("-m", "unittest", "discover", "-s", "tests")
