---
name: pe-architecture-verifier
description: Verify that Windows PE executables, DLLs, and Python extensions use an expected machine architecture.
---

# PE architecture verifier

Use this skill after producing Windows native artifacts and before publishing
or testing them. A filename, build platform, or wheel tag is not architecture
proof; inspect each PE header.

## Inputs

- One or more `.exe`, `.dll`, or `.pyd` paths.
- Expected machine type: `ARM64`, `AMD64`, `ARM64EC`, or `X86`.
- Optional JSON evidence path.

## Procedure

1. Confirm each input is a regular file.
2. Run:

   ```powershell
   .\.github\skills\pe-architecture-verifier\scripts\Test-PeArchitecture.ps1 `
     -Path <artifact-paths> `
     -ExpectedMachine ARM64 `
     -OutputPath evidence\pe-architecture.json
   ```

3. Preserve the JSON report with the build artifacts.
4. Fail the build if a file is not a valid PE image or its machine type differs
   from the expected value.

## Verification

The report must identify every input and show the expected machine value:

| Architecture | PE machine |
|---|---|
| ARM64 | `0xAA64` |
| AMD64 | `0x8664` |
| ARM64EC | `0xA641` |
| X86 | `0x014C` |

Do not infer architecture from `PROCESSOR_ARCHITECTURE`, compiler selection,
directory names, or package tags.
