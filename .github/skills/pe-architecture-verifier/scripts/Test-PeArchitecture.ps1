[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string[]] $Path,

    [Parameter(Mandatory)]
    [ValidateSet("ARM64", "AMD64", "ARM64EC", "X86")]
    [string] $ExpectedMachine,

    [string] $OutputPath
)

$ErrorActionPreference = "Stop"

$machineTypes = @{
    ARM64   = [uint16]0xAA64
    AMD64   = [uint16]0x8664
    ARM64EC = [uint16]0xA641
    X86     = [uint16]0x014C
}
$expectedValue = $machineTypes[$ExpectedMachine]
$results = foreach ($itemPath in $Path) {
    $item = Get-Item -LiteralPath $itemPath -ErrorAction Stop
    if ($item.PSIsContainer) {
        throw "Expected a PE file but received directory '$($item.FullName)'."
    }

    $bytes = [System.IO.File]::ReadAllBytes($item.FullName)
    if ($bytes.Length -lt 64 -or [BitConverter]::ToUInt16($bytes, 0) -ne 0x5A4D) {
        throw "'$($item.FullName)' is not a valid DOS/PE image."
    }

    $peOffset = [BitConverter]::ToInt32($bytes, 0x3C)
    if ($peOffset -lt 0 -or $peOffset + 6 -gt $bytes.Length) {
        throw "'$($item.FullName)' contains an invalid PE header offset."
    }
    if ([BitConverter]::ToUInt32($bytes, $peOffset) -ne 0x00004550) {
        throw "'$($item.FullName)' does not contain a valid PE signature."
    }

    $machine = [BitConverter]::ToUInt16($bytes, $peOffset + 4)
    [pscustomobject]@{
        path            = $item.FullName
        machine         = "0x$($machine.ToString('X4'))"
        expectedMachine = "0x$($expectedValue.ToString('X4'))"
        architecture    = $ExpectedMachine
        matches         = $machine -eq $expectedValue
    }
}

$json = @($results) | ConvertTo-Json -Depth 3
if ($OutputPath) {
    $parent = Split-Path -Parent $OutputPath
    if ($parent) {
        New-Item -ItemType Directory -Force $parent | Out-Null
    }
    $json | Set-Content -Encoding utf8 $OutputPath
}
$json

$mismatches = @($results | Where-Object { -not $_.matches })
if ($mismatches.Count -ne 0) {
    $actual = $mismatches | ForEach-Object { "$($_.path)=$($_.machine)" }
    throw "Expected $ExpectedMachine PE machine 0x$($expectedValue.ToString('X4')); found $($actual -join ', ')."
}
