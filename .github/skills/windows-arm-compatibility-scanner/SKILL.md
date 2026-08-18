---
name: windows-arm-compatibility-scanner
description: Find evidence-backed x86 intrinsics, assembly, architecture guards, hard-coded x64 paths, and missing Windows Arm64 CI coverage.
---

# Windows Arm compatibility scanner

Run this skill after repository profiling and before architecture selection.

## Procedure

```powershell
python -m portpilot.analysis.compatibility_scanner `
  --manifest <portpilot.yml> `
  --repository <checkout> `
  --output <run>\findings.json
```

The scanner emits one bounded finding per matched rule and file. Every finding
includes the source location, exact evidence, impact, severity, status, and
proposed remediation skill.

## Constraints

- Findings are evidence, not automatic proof that code is broken on Arm64.
- Do not rewrite source during scanning.
- Do not classify ordinary portable C/C++ as architecture-specific.
- Preserve findings even when the initial Arm64 build later succeeds.
