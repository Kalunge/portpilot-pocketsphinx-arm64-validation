# PortPilot Repository Analysis Skills

## Purpose

H2 converts repository inspection into four reusable, schema-backed skills:

1. `repository-profiler`
2. `dependency-inventory`
3. `windows-arm-compatibility-scanner`
4. `architecture-selector`

The skills perform read-only analysis. They do not edit the target repository,
install dependencies, or claim that a static match is a confirmed build defect.

## Running the complete analysis

```powershell
python scripts\run_analysis.py `
  --manifest manifests\<project>\portpilot.yml `
  --repository <clean-checkout> `
  --output-directory runs\<run-id>
```

Generated files:

```text
architecture-decision.json
dependencies.json
findings.json
inventory.json
```

Each output is validated before it is written. Invalid findings or decisions
fail the analysis rather than producing success-shaped output.

## Analysis behavior

### Repository profiler

- Counts source languages.
- Detects build and package systems from repository files.
- Records checked-in `.exe`, `.dll`, `.pyd`, and `.lib` files.
- Reads PE machine values for executable images.
- Reports COFF archives as unknown until archive-aware inspection is added.

### Dependency inventory

- Detects `find_package`, `FetchContent_Declare`, independent bundled CMake
  projects, `vcpkg.json`, `pyproject.toml`, and `requirements.txt`.
- Records architecture, role, and in-process status as unknown unless verified.
- Does not interpret an out-of-process x64 build tool as an Arm64EC requirement.

### Compatibility scanner

- Detects x86 SIMD identifiers, inline or standalone assembly, architecture
  guards, hard-coded x64 paths, and Windows workflows without Arm64 coverage.
- Emits the exact source path, line, evidence, impact, and proposed skill.
- Treats matches as review items because correctly guarded platform-specific
  code may already be portable.

### Architecture selector

- Prefers native Arm64.
- Selects Arm64EC only for a verified x64-only in-process dependency.
- Returns `blocked` for unresolved blocker findings.
- Keeps assembly and SIMD findings as review evidence without automatically
  changing the architecture.

## Real-repository validation

Both projects were analyzed from clean detached checkouts at their pinned
commits.

| Project | Dependencies | Findings | Decision |
|---|---:|---:|---|
| PocketSphinx 5.1.1 | 8 | 3 | Native Arm64 |
| whisper.cpp 1.9.2 | 30 | 23 | Native Arm64 |

PocketSphinx findings identify two guarded assembly sites and one architecture
guard for review. The successful reference port confirms these do not prevent
native Arm64.

whisper.cpp findings identify architecture-dispatched x86 SIMD and assembly
surfaces plus the two verified Windows workflows that omit Arm64. No verified
x64-only in-process dependency was found, so native Arm64 remains the selected
target.

The dependency count is an inventory, not a claim that every optional backend
is enabled by the reference build. H4 will probe the selected build's effective
dependency graph.

## Tests

```powershell
python -m unittest discover -s tests -v
python scripts\validate_contracts.py
```

Fixtures cover native Arm64 selection, Arm64EC selection for an x64-only
in-process library, rejection of Arm64EC for an x64-only build tool, blocker
handling, x86 intrinsic detection, CMake path detection, Windows CI gaps, and
schema validation.
