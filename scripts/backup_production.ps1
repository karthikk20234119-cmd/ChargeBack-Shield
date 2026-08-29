# PowerShell Backup Script — Chargeback Shield Task 8.4
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootDir = Split-Path -Parent $scriptDir

$pythonExe = Join-Path $rootDir "venv\Scripts\python.exe"
$backupScript = Join-Path $scriptDir "backup_production.py"

if (Test-Path $pythonExe) {
    & $pythonExe $backupScript
} else {
    python $backupScript
}
