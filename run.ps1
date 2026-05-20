# Windows PowerShell run script for B.R.I.D.G.E.
# Assumes virtual environment is configured in .venv/

$VenvPath = Join-Path $PSScriptRoot ".venv"
$ActivateScript = Join-Path $VenvPath "Scripts\Activate.ps1"

if (Test-Path $ActivateScript) {
    Write-Host "Activating python virtual environment at $VenvPath..." -ForegroundColor Cyan
    . $ActivateScript
} else {
    Write-Host "[WARNING]: Python virtual environment not found. Running with global python context." -ForegroundColor Yellow
}

Write-Host "Launching B.R.I.D.G.E...." -ForegroundColor Green
python main.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR]: Application crashed or terminated with error exit code: $LASTEXITCODE" -ForegroundColor Red
} else {
    Write-Host "Application terminated cleanly." -ForegroundColor Green
}
