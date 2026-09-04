param(
    [switch]$WhatIf,
    [string]$ProbePath = "",
    [switch]$ProbeOnly,
    [string]$WingetExe = ""
)

$ErrorActionPreference = "Stop"

function Find-Obsidian {
    $candidates = @()
    if ($ProbePath) {
        $candidates += $ProbePath
    }
    if ($ProbeOnly) {
        return $candidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
    }
    $command = Get-Command "Obsidian.exe" -ErrorAction SilentlyContinue
    if ($null -ne $command) {
        $candidates += $command.Source
    }
    $candidates += (Join-Path $env:LOCALAPPDATA "Obsidian\Obsidian.exe")
    $candidates += (Join-Path $env:LOCALAPPDATA "Programs\Obsidian\Obsidian.exe")
    return $candidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
}

function Find-Winget {
    if ($WingetExe) {
        return $WingetExe
    }
    $command = Get-Command "winget.exe" -ErrorAction SilentlyContinue
    if ($null -ne $command) {
        return $command.Source
    }
    $alias = Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps\winget.exe"
    if (Test-Path -LiteralPath $alias -PathType Leaf) {
        return $alias
    }
    $package = Get-AppxPackage -Name Microsoft.DesktopAppInstaller -ErrorAction SilentlyContinue
    if ($null -ne $package) {
        $packaged = Join-Path $package.InstallLocation "winget.exe"
        if (Test-Path -LiteralPath $packaged -PathType Leaf) {
            return $packaged
        }
    }
    throw "Windows App Installer is present but winget.exe could not be resolved"
}

$installed = Find-Obsidian
if ($installed) {
    Write-Host "[obsidian] installed"
    exit 0
}

if ($WhatIf) {
    Write-Host "[obsidian] would install Obsidian.Obsidian with winget"
    exit 0
}

$resolvedWinget = Find-Winget
& $resolvedWinget install --id Obsidian.Obsidian --exact --silent --accept-package-agreements --accept-source-agreements
if ($LASTEXITCODE -ne 0) {
    throw "winget failed to install Obsidian with exit code $LASTEXITCODE"
}

$installed = Find-Obsidian
if (-not $installed) {
    throw "Obsidian installation completed but Obsidian.exe was not found"
}
Write-Host "[obsidian] installed"
