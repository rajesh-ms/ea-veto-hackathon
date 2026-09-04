$ErrorActionPreference = "Stop"

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Label,
        [Parameter(Mandatory = $true)]
        [string[]]$Command
    )

    Write-Host "[live-acceptance] $Label"
    & $Command[0] $Command[1..($Command.Length - 1)]
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

Invoke-Checked "offline acceptance" @(
    "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "tools/acceptance.ps1"
)
Invoke-Checked "live extension contract" @(
    "python", "-m", "pytest", "tests/e2e/test_live_extension_contract.py", "-q"
)
Invoke-Checked "sanitized live evidence" @(
    "python", "tools/verify_live_evidence.py", "artifacts/live-scout-evidence.json"
)
Invoke-Checked "complete desktop recording" @(
    "python", "tools/verify_demo_video.py", "artifacts/ea-copilot-scout-demo.webm"
)
Invoke-Checked "demo privacy" @(
    "python", "tools/verify_demo_privacy.py",
    "artifacts/ea-copilot-scout-demo.manifest.json",
    "artifacts/live-scout-evidence.json",
    "demo-vault"
)

Write-Host "[live-acceptance] all gates passed"
