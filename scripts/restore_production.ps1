# PowerShell Restore Script — Chargeback Shield Task 8.4
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootDir = Split-Path -Parent $scriptDir

$pythonExe = Join-Path $rootDir "venv\Scripts\python.exe"
$restoreScript = Join-Path $scriptDir "restore_production.py"

if (Test-Path $pythonExe) {
    & $pythonExe $restoreScript $args
} else {
    python $restoreScript $args
}
