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

```powershell
.\.github\skills\pe-architecture-verifier\scripts\Test-PeArchitecture.ps1 `
  -Path <artifact-paths> -ExpectedMachine ARM64 `
  -OutputPath evidence\pe-architecture.json
```

Preserve the report and fail if a file is not a PE image or does not match.
