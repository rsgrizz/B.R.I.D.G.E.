# Created by: Randy Grizzelli
# Email: grizzellir@gmail.com
# GitHub: https://github.com/rsgrizz
# Version: v.6
# Date: 5/21/2026
# Purpose: Build, validate, and package B.R.I.D.G.E. using PyInstaller in one-directory mode.

# Set error action to Stop to fail fast on errors
$ErrorActionPreference = "Stop"

Write-Host "==================================================" -ForegroundColor Magenta
Write-Host "         B.R.I.D.G.E. Build & Packaging Tool      " -ForegroundColor Magenta
Write-Host "==================================================" -ForegroundColor Magenta

# 1. Virtual Environment Activation
$VenvPath = Join-Path $PSScriptRoot ".venv"
$ActivateScript = Join-Path $VenvPath "Scripts\Activate.ps1"

if (Test-Path $ActivateScript) {
    Write-Host "Activating virtual environment at $VenvPath..." -ForegroundColor Cyan
    . $ActivateScript
} else {
    Write-Host "Running in active environment context..." -ForegroundColor Yellow
}

# 2. Run prior build artifacts cleaning
Write-Host "Cleaning up prior build artifacts..." -ForegroundColor Cyan
$BuildDir = Join-Path $PSScriptRoot "build"
$DistDir = Join-Path $PSScriptRoot "dist"

if (Test-Path $BuildDir) {
    Remove-Item -Recurse -Force $BuildDir
    Write-Host "Removed prior build/ directory." -ForegroundColor Gray
}
if (Test-Path $DistDir) {
    Remove-Item -Recurse -Force $DistDir
    Write-Host "Removed prior dist/ directory." -ForegroundColor Gray
}

# 3. Run full test suite before packaging
Write-Host "Running complete automated test suite..." -ForegroundColor Cyan
python -m unittest discover -s tests -v

# 4. Run PyInstaller packaging
Write-Host "Invoking PyInstaller packaging (One Directory Mode)..." -ForegroundColor Green
pyinstaller --clean BRIDGE.spec

# Copy tools directory to adjacent distribution root (dist/BRIDGE/tools)
Write-Host "Copying tools directory to adjacent distribution root..." -ForegroundColor Cyan
$DistToolsDir = Join-Path $PSScriptRoot "dist\BRIDGE\tools"
if (-not (Test-Path $DistToolsDir)) {
    New-Item -ItemType Directory -Force -Path $DistToolsDir | Out-Null
}
Copy-Item -Path (Join-Path $PSScriptRoot "tools\*") -Destination $DistToolsDir -Recurse -Force

# Copy image/icon assets next to the packaged executable for runtime branding.
Write-Host "Copying application assets to adjacent distribution root..." -ForegroundColor Cyan
$DistAssetsDir = Join-Path $PSScriptRoot "dist\BRIDGE\app\assets"
if (-not (Test-Path $DistAssetsDir)) {
    New-Item -ItemType Directory -Force -Path $DistAssetsDir | Out-Null
}
Copy-Item -Path (Join-Path $PSScriptRoot "app\assets\*") -Destination $DistAssetsDir -Recurse -Force

# 5. Verify the package output structure
$PackagedExe = Join-Path $PSScriptRoot "dist\BRIDGE\BRIDGE.exe"
$PackagedTools = Join-Path $PSScriptRoot "dist\BRIDGE\tools"
$PackagedAssets = Join-Path $PSScriptRoot "dist\BRIDGE\app\assets"

if (Test-Path $PackagedExe) {
    Write-Host "`n==================================================" -ForegroundColor Green
    Write-Host "               PACKAGING COMPLETE                 " -ForegroundColor Green
    Write-Host "==================================================" -ForegroundColor Green
    Write-Host "Distribution output folder: $(Join-Path $PSScriptRoot 'dist\BRIDGE')" -ForegroundColor Cyan
    Write-Host "Package Executable: $PackagedExe" -ForegroundColor Cyan
    Write-Host "Bundled Tools Directory: $PackagedTools" -ForegroundColor Cyan
    Write-Host "Bundled Assets Directory: $PackagedAssets" -ForegroundColor Cyan
    Write-Host "Application successfully packaged in onedir mode." -ForegroundColor Green
} else {
    Write-Host "[ERROR]: Packaged executable not found at expected destination: $PackagedExe" -ForegroundColor Red
    exit 1
}
