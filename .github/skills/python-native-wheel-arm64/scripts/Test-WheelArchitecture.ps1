[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string] $WheelPath,

    [string] $OutputPath
)

$ErrorActionPreference = "Stop"
$wheel = Get-Item -LiteralPath $WheelPath -ErrorAction Stop
if ($wheel.Name -notmatch "-win_arm64\.whl$") {
    throw "Expected a win_arm64 wheel, received '$($wheel.Name)'."
}

Add-Type -AssemblyName System.IO.Compression.FileSystem
$extractDir = Join-Path ([System.IO.Path]::GetTempPath()) "portpilot-wheel-$([guid]::NewGuid())"
New-Item -ItemType Directory $extractDir | Out-Null

try {
    [System.IO.Compression.ZipFile]::ExtractToDirectory($wheel.FullName, $extractDir)
    $nativeFiles = @(Get-ChildItem $extractDir -Recurse -File |
        Where-Object { $_.Extension -in ".pyd", ".dll", ".exe" })
    if ($nativeFiles.Count -eq 0) {
        throw "Wheel '$($wheel.Name)' contains no native PE files."
    }

    $verifier = Join-Path $PSScriptRoot "..\..\pe-architecture-verifier\scripts\Test-PeArchitecture.ps1"
    $nativeReportPath = Join-Path $extractDir "native-architecture.json"
    & $verifier -Path $nativeFiles.FullName -ExpectedMachine ARM64 -OutputPath $nativeReportPath | Out-Null
    $nativeReport = Get-Content $nativeReportPath -Raw | ConvertFrom-Json

    $report = [pscustomobject]@{
        wheel          = $wheel.Name
        platformTag    = "win_arm64"
        nativeBinaries = @($nativeReport)
    }
    $json = $report | ConvertTo-Json -Depth 5
    if ($OutputPath) {
        $parent = Split-Path -Parent $OutputPath
        if ($parent) {
            New-Item -ItemType Directory -Force $parent | Out-Null
        }
        $json | Set-Content -Encoding utf8 $OutputPath
    }
    $json
}
finally {
    Remove-Item -LiteralPath $extractDir -Recurse -Force
}
