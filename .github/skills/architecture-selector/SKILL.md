---
name: architecture-selector
description: Select native Arm64 or Arm64EC from repository inventory, dependency architecture evidence, and compatibility findings.
---

# Architecture selector

Prefer native Arm64. Select Arm64EC only when a verified x64-only in-process
dependency prevents a fully native process.

## Procedure

```powershell
python -m portpilot.analysis.architecture_selector `
  --manifest <portpilot.yml> `
  --inventory <run>\inventory.json `
  --dependencies <run>\dependencies.json `
  --findings <run>\findings.json `
  --output <run>\architecture-decision.json
```

## Output

The decision records the selected architecture, confidence, rationale, evidence,
and blockers. Assembly or intrinsic findings remain remediation blockers but do
not automatically justify Arm64EC.

Never choose architecture from processor environment variables, directory
names, package tags, or assumptions about a dependency.
