# PyInstaller Windows Packaging Script
# Packages B.R.I.D.G.E. into standalone one-directory mode.

$VenvPath = Join-Path $PSScriptRoot ".venv"
$ActivateScript = Join-Path $VenvPath "Scripts\Activate.ps1"

if (Test-Path $ActivateScript) {
    Write-Host "Activating virtual environment..." -ForegroundColor Cyan
    . $ActivateScript
}

Write-Host "Verifying PyInstaller installation..." -ForegroundColor Cyan
try {
    Get-Command pyinstaller -ErrorAction Stop > $null
} catch {
    Write-Host "PyInstaller not found. Installing now..." -ForegroundColor Yellow
    pip install pyinstaller
}

Write-Host "Beginning PyInstaller execution (One Directory Mode)..." -ForegroundColor Green

# Package parameters:
# --onedir: Build in one-directory mode (required)
# --noconsole: Disable stdout command console (standard for GUI applications)
# --add-data: Include custom directories (e.g. tools, logs) in bundle
# --name: Define output package name

pyinstaller --onedir `
            --noconsole `
            --add-data "tools;tools" `
            --name "BRIDGE" `
            main.py

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n[SUCCESS]: Application successfully packaged." -ForegroundColor Green
    Write-Host "Distribution output folder: $(Join-Path $PSScriptRoot 'dist\BRIDGE')" -ForegroundColor Cyan
    Write-Host "External tool binaries have been bundled in dist\BRIDGE\tools\" -ForegroundColor Cyan
} else {
    Write-Host "`n[ERROR]: Packaging pipeline failed." -ForegroundColor Red
}
