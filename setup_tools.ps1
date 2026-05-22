# B.R.I.D.G.E. External Tool Setup
# Installs/copies qemu-img and ewftools into the local tools/ directory.

param(
    [switch]$Force,
    [switch]$SkipQemu,
    [switch]$SkipEwf
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ToolsDir = Join-Path $PSScriptRoot "tools"
$EwfToolsUrl = "https://github.com/alpine-sec/ewf-tools/releases/download/v20230405/ewftools-x64.zip"
$EwfToolsSource = "alpine-sec/ewf-tools v20230405, built from libyal/libewf"
$QemuPackageId = "cloudbase.qemu-img"

function Write-Step {
    param([string]$Message)
    Write-Host "[SETUP] $Message" -ForegroundColor Cyan
}

function Copy-MatchingFiles {
    param(
        [string]$SourceDir,
        [string[]]$Patterns,
        [string]$DestinationDir
    )

    foreach ($pattern in $Patterns) {
        Get-ChildItem -Path (Join-Path $SourceDir $pattern) -File -ErrorAction SilentlyContinue |
            Copy-Item -Destination $DestinationDir -Force
    }
}

function Find-QemuPackageDir {
    $searchRoots = @(
        (Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages"),
        $env:ProgramFiles,
        ${env:ProgramFiles(x86)}
    ) | Where-Object { $_ -and (Test-Path $_) }

    foreach ($root in $searchRoots) {
        $match = Get-ChildItem -LiteralPath $root -Recurse -Filter "qemu-img.exe" -File -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 1

        if ($match) {
            return $match.Directory.FullName
        }
    }

    return $null
}

function Install-QemuImg {
    $target = Join-Path $ToolsDir "qemu-img.exe"
    if ((Test-Path $target) -and -not $Force) {
        Write-Step "qemu-img.exe already exists in tools/. Use -Force to refresh it."
        return
    }

    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw "winget is required to install qemu-img automatically. Install qemu-img manually and place qemu-img.exe plus DLLs in tools/."
    }

    Write-Step "Installing qemu-img through winget package $QemuPackageId."
    winget install --id $QemuPackageId --exact --accept-package-agreements --accept-source-agreements --silent

    $qemuDir = Find-QemuPackageDir
    if (-not $qemuDir) {
        throw "qemu-img.exe was not found after winget installation."
    }

    Write-Step "Copying qemu-img executable and DLLs from $qemuDir."
    Copy-MatchingFiles -SourceDir $qemuDir -Patterns @("*.exe", "*.dll", "LICENSE*", "COPYING*") -DestinationDir $ToolsDir
}

function Install-EwfTools {
    $target = Join-Path $ToolsDir "ewfexport.exe"
    if ((Test-Path $target) -and -not $Force) {
        Write-Step "ewfexport.exe already exists in tools/. Use -Force to refresh it."
        return
    }

    $zipPath = Join-Path $env:TEMP "bridge-ewftools-x64.zip"
    $extractDir = Join-Path $env:TEMP "bridge-ewftools-x64"

    if (Test-Path $extractDir) {
        Remove-Item -LiteralPath $extractDir -Recurse -Force
    }

    Write-Step "Downloading ewftools from $EwfToolsUrl."
    Invoke-WebRequest -Uri $EwfToolsUrl -OutFile $zipPath

    Write-Step "Extracting ewftools archive."
    Expand-Archive -LiteralPath $zipPath -DestinationPath $extractDir -Force

    $ewfExport = Get-ChildItem -LiteralPath $extractDir -Recurse -Filter "ewfexport.exe" -File |
        Select-Object -First 1

    if (-not $ewfExport) {
        throw "ewfexport.exe was not found inside the downloaded ewftools archive."
    }

    $ewfDir = $ewfExport.Directory.FullName
    Write-Step "Copying ewftools executables and runtime DLLs from $ewfDir."
    Copy-MatchingFiles -SourceDir $ewfDir -Patterns @("ewf*.exe", "*.dll", "COPYING*", "LICENSE") -DestinationDir $ToolsDir
}

function Write-ToolManifest {
    $manifestPath = Join-Path $ToolsDir "TOOLS_MANIFEST.txt"
    $lines = @(
        "B.R.I.D.G.E. external tools manifest",
        "Generated: $(Get-Date -Format o)",
        "",
        "qemu-img source: winget package $QemuPackageId",
        "ewftools source: $EwfToolsSource",
        "ewftools URL: $EwfToolsUrl",
        ""
    )

    foreach ($name in @("qemu-img.exe", "ewfexport.exe", "libewf.dll", "zlib.dll")) {
        $path = Join-Path $ToolsDir $name
        if (Test-Path $path) {
            $hash = Get-FileHash -Algorithm SHA256 -LiteralPath $path
            $lines += "$name SHA256 $($hash.Hash)"
        }
    }

    Set-Content -LiteralPath $manifestPath -Value $lines -Encoding UTF8
}

function Test-InstalledTools {
    $qemu = Join-Path $ToolsDir "qemu-img.exe"
    $ewf = Join-Path $ToolsDir "ewfexport.exe"

    if (-not (Test-Path $qemu)) {
        throw "Missing required tool: $qemu"
    }
    if (-not (Test-Path $ewf)) {
        throw "Missing required tool: $ewf"
    }

    Write-Step "Verifying ewfexport."
    & $ewf -V

    Write-Step "Verifying qemu-img."
    & $qemu --version
}

Write-Host "==================================================" -ForegroundColor Magenta
Write-Host "         B.R.I.D.G.E. External Tool Setup         " -ForegroundColor Magenta
Write-Host "==================================================" -ForegroundColor Magenta

New-Item -ItemType Directory -Force -Path $ToolsDir | Out-Null

if (-not $SkipQemu) {
    Install-QemuImg
}

if (-not $SkipEwf) {
    Install-EwfTools
}

Write-ToolManifest
Test-InstalledTools

Write-Host "`n[OK] External tools are ready in $ToolsDir" -ForegroundColor Green
