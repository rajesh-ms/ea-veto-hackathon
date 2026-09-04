param(
    [string]$Output = "artifacts\ea-copilot-scout-demo.webm",
    [int]$DurationSeconds = 180,
    [int]$FrameRate = 15,
    [string]$FfmpegExe = "",
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path -LiteralPath (Split-Path -Parent $PSScriptRoot)).Path
$outputPath = [System.IO.Path]::GetFullPath((Join-Path $repositoryRoot $Output))
if (-not $outputPath.StartsWith($repositoryRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Desktop recording output must remain inside the repository"
}

if (-not $FfmpegExe) {
    $command = Get-Command "ffmpeg.exe" -ErrorAction SilentlyContinue
    if ($null -ne $command) {
        $FfmpegExe = $command.Source
    }
}
if (-not $FfmpegExe) {
    $packageRoot = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages"
    if (Test-Path -LiteralPath $packageRoot -PathType Container) {
        $FfmpegExe = Get-ChildItem -Path $packageRoot -Filter "ffmpeg.exe" -Recurse -File -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -match "Gyan\.FFmpeg" } |
            Select-Object -ExpandProperty FullName -First 1
    }
}
if (-not $FfmpegExe -or -not (Test-Path -LiteralPath $FfmpegExe -PathType Leaf)) {
    throw "A verified ffmpeg.exe capture backend is required"
}
if ($DurationSeconds -lt 5 -or $DurationSeconds -gt 900) {
    throw "DurationSeconds must be between 5 and 900"
}

if ($WhatIf) {
    Write-Host "[desktop-demo] would capture the desktop to $Output"
    exit 0
}

New-Item -ItemType Directory -Path (Split-Path -Parent $outputPath) -Force | Out-Null
& $FfmpegExe -y -f gdigrab -framerate $FrameRate -i desktop -t $DurationSeconds -c:v libvpx-vp9 -deadline realtime -cpu-used 6 -b:v 2M -an $outputPath
if ($LASTEXITCODE -ne 0) {
    throw "Desktop recording failed with exit code $LASTEXITCODE"
}
if (-not (Test-Path -LiteralPath $outputPath -PathType Leaf)) {
    throw "Desktop recording did not create an output file"
}
Write-Host "[desktop-demo] recording created"
