# PortPilot Contracts

## Purpose

PortPilot uses versioned manifests and JSON Schemas as the boundary between
application-specific knowledge and the reusable engine. Agents, skills, local
commands, and CI must communicate through these contracts rather than relying
on conversational state.

## Application manifest

Each application supplies one `portpilot.yml` validated by
`schemas/portpilot.schema.json`.

Reference manifests:

- `manifests/pocketsphinx/portpilot.yml`
- `manifests/whisper-cpp/portpilot.yml`

The manifest records:

- Project identity and license
- Immutable repository revision
- Source preparation, patches, and checksummed resources
- Baseline and target runners and architectures
- Toolchain dependencies and probes
- Structured configure and build commands
- Tests, known-failure policy, and deterministic scenarios
- Architecture checks and optional package validation
- Artifacts and required evidence records

Commands separate the executable from its argument list. This lets H3 enforce
command policy without parsing arbitrary shell scripts.

## Template variables

The orchestrator will resolve these values before executing a command:

| Variable | Meaning |
|---|---|
| `${phase}` | `baseline` or `target` |
| `${sourceDirectory}` | Manifest build source directory |
| `${buildDirectory}` | Phase-expanded build directory |
| `${platform}` | CMake platform for the current build variant |
| `${configuration}` | CMake configuration |
| `${wheel}` | Downloaded wheel path in a clean-install job |

Unknown variables must be rejected. Values are passed as individual process
arguments rather than concatenated into a shell command.

Configure commands with `appendDefinitions: true` receive one
`-Dname=value` argument per entry in `build.definitions`, sorted by name.
Boolean values are rendered as CMake `ON` or `OFF`. This preserves the
one-manifest-item-to-one-process-argument invariant.

All manifest paths are relative to the run root. Absolute paths and `..`
segments are rejected by the schema.

## Run-state schemas

| Schema | Durable output |
|---|---|
| `project.schema.json` | Run identity, source, target, lifecycle status |
| `inventory.schema.json` | Languages, build systems, packages, native dependencies, binaries |
| `finding.schema.json` | One evidence-backed compatibility finding |
| `task.schema.json` | One bounded remediation task and its acceptance checks |
| `result.schema.json` | One command execution result and its artifacts |
| `report.schema.json` | Final gates, evidence, risks, and release verdict |

Expected run layout:

```text
runs/<run-id>/
  project.json
  inventory.json
  findings/
  tasks/
  results/
  evidence/
  report.json
```

H2 and H3 may extend schemas only through a reviewed schema-version change.
Unknown properties are rejected to prevent silent contract drift.

## Validation

Install the contract validation dependencies:

```powershell
python -m pip install -r requirements-contracts.txt
```

Validate every schema and application manifest:

```powershell
python scripts\validate_contracts.py
```

The validator also confirms that a manifest without a pinned source revision is
rejected.
