param(
    [string]$StateRoot = (Join-Path $env:USERPROFILE ".scout"),
    [string]$RepositoryRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$PythonExe = "python",
    [switch]$Uninstall,
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"

function Write-Utf8NoBom {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$Content
    )

    $encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Content, $encoding)
}

$resolvedRepository = (Resolve-Path -LiteralPath $RepositoryRoot).Path
$skillSource = Join-Path $resolvedRepository "integrations\scout\ea-copilot\SKILL.md"
if (-not (Test-Path -LiteralPath $skillSource -PathType Leaf)) {
    throw "Scout skill source was not found: $skillSource"
}

$skillTarget = Join-Path $StateRoot "skills\ea-copilot"
$storePath = Join-Path $StateRoot "m-mcp-servers.json"

if ($WhatIf) {
    $action = if ($Uninstall) { "remove" } else { "install" }
    Write-Host "[scout-integration] would $action EA Copilot in $StateRoot"
    exit 0
}

New-Item -ItemType Directory -Path $StateRoot -Force | Out-Null

if ($Uninstall) {
    if (Test-Path -LiteralPath $storePath -PathType Leaf) {
        $data = Get-Content -LiteralPath $storePath -Raw | ConvertFrom-Json
        if ($null -ne $data.servers) {
            $data.servers.PSObject.Properties.Remove("ea-copilot")
            Write-Utf8NoBom -Path $storePath -Content ($data | ConvertTo-Json -Depth 12)
        }
    }
    if (Test-Path -LiteralPath $skillTarget -PathType Container) {
        $resolvedState = (Resolve-Path -LiteralPath $StateRoot).Path
        $resolvedSkill = (Resolve-Path -LiteralPath $skillTarget).Path
        if (-not $resolvedSkill.StartsWith($resolvedState, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to remove a skill outside the Scout state root"
        }
        Remove-Item -LiteralPath $resolvedSkill -Recurse -Force
    }
    Write-Host "[scout-integration] removed EA Copilot"
    exit 0
}

if (Test-Path -LiteralPath $storePath -PathType Leaf) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmssfff"
    Copy-Item -LiteralPath $storePath -Destination "$storePath.backup-$stamp" -Force
    $data = Get-Content -LiteralPath $storePath -Raw | ConvertFrom-Json
} else {
    $data = [PSCustomObject]@{ servers = [PSCustomObject]@{} }
}

if ($null -eq $data.servers) {
    $data | Add-Member -MemberType NoteProperty -Name servers -Value ([PSCustomObject]@{})
}

$entry = [PSCustomObject]@{
    builtin = $false
    config = [PSCustomObject]@{
        name = "EA Copilot"
        type = "stdio"
        command = $PythonExe
        args = [object[]]@("-m", "ea_copilot.integrations")
        timeout = 300000
    }
    tools = [object[]]@()
}

if ($null -ne $data.servers.PSObject.Properties["ea-copilot"]) {
    $data.servers."ea-copilot" = $entry
} else {
    $data.servers | Add-Member -MemberType NoteProperty -Name "ea-copilot" -Value $entry
}

New-Item -ItemType Directory -Path $skillTarget -Force | Out-Null
Copy-Item -LiteralPath $skillSource -Destination (Join-Path $skillTarget "SKILL.md") -Force
Write-Utf8NoBom -Path $storePath -Content ($data | ConvertTo-Json -Depth 12)

Write-Host "[scout-integration] installed EA Copilot stdio MCP and skill"
