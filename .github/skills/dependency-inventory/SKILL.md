---
name: dependency-inventory
description: Inventory CMake, bundled, vcpkg, and Python dependencies and record known architecture availability.
---

# Dependency inventory

Use this skill before selecting native Arm64 or Arm64EC.

## Procedure

```powershell
python -m portpilot.analysis.dependency_inventory `
  --manifest <portpilot.yml> `
  --repository <checkout> `
  --output <run>\dependencies.json
```

The first pass detects declared dependencies and records unknown architecture
availability, role, and in-process status rather than guessing. Later
dependency remediation may enrich the same contract with verified `x64`,
`arm64`, `arm64ec`, or `portable` values.

An x64-only in-process dependency is architecture-decision evidence. A build
tool used out of process is not, by itself, a reason to select Arm64EC.
