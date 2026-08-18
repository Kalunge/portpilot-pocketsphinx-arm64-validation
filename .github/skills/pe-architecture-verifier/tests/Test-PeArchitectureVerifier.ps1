$ErrorActionPreference = "Stop"

$fixture = Join-Path ([System.IO.Path]::GetTempPath()) "portpilot-amd64-$([guid]::NewGuid()).exe"
$report = Join-Path ([System.IO.Path]::GetTempPath()) "portpilot-amd64-$([guid]::NewGuid()).json"
$verifier = Join-Path $PSScriptRoot "..\scripts\Test-PeArchitecture.ps1"

try {
    $bytes = [byte[]]::new(128)
    [BitConverter]::GetBytes([uint16]0x5A4D).CopyTo($bytes, 0)
    [BitConverter]::GetBytes([int32]0x40).CopyTo($bytes, 0x3C)
    [BitConverter]::GetBytes([uint32]0x00004550).CopyTo($bytes, 0x40)
    [BitConverter]::GetBytes([uint16]0x8664).CopyTo($bytes, 0x44)
    [System.IO.File]::WriteAllBytes($fixture, $bytes)

    & $verifier -Path $fixture -ExpectedMachine AMD64 -OutputPath $report | Out-Null
    $result = Get-Content $report -Raw | ConvertFrom-Json
    if (-not $result.matches -or $result.machine -ne "0x8664") {
        throw "The verifier did not accept the AMD64 fixture."
    }

    $rejectedMismatch = $false
    try {
        & $verifier -Path $fixture -ExpectedMachine ARM64 | Out-Null
    }
    catch {
        $rejectedMismatch = $true
    }
    if (-not $rejectedMismatch) {
        throw "The verifier accepted an AMD64 fixture as ARM64."
    }
}
finally {
    Remove-Item -LiteralPath $fixture -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $report -Force -ErrorAction SilentlyContinue
}

"PE architecture verifier fixture tests passed."
