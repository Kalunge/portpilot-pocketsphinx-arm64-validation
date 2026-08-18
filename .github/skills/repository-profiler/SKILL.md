---
name: repository-profiler
description: Inventory a repository's languages, build systems, package systems, native dependencies, and checked-in binaries for Windows Arm porting.
---

# Repository profiler

Use this skill at the start of every PortPilot run, before proposing
architecture or source changes.

## Inputs

- A schema-valid `portpilot.yml`.
- A clean checkout at the manifest's pinned revision.

## Procedure

```powershell
python -m portpilot.analysis.repository_profiler `
  --manifest <portpilot.yml> `
  --repository <checkout> `
  --output <run>\inventory.json
```

For the complete H2 analysis pipeline, use:

```powershell
python scripts\run_analysis.py `
  --manifest <portpilot.yml> `
  --repository <checkout> `
  --output-directory <run>
```

## Output

`inventory.json`, validated by `schemas/inventory.schema.json`.

Do not infer support from repository labels or documentation alone. Record
checked-in binaries by their actual PE machine type.
