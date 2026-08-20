# PortPilot Orchestrator

## Purpose

PortPilot provides a resumable CLI around the manifest, analysis, planning, and
execution contracts. H4 adds policy-constrained build and validation handlers.

Install the development CLI:

```powershell
python -m pip install -e .
```

## Commands

Create or resume all currently implemented stages:

```powershell
portpilot run `
  --manifest manifests\whisper-cpp\portpilot.yml `
  --repository C:\src\whisper.cpp `
  --runs-directory runs `
  --run-id whisper-demo
```

Run only analysis:

```powershell
portpilot analyze `
  --manifest manifests\whisper-cpp\portpilot.yml `
  --repository C:\src\whisper.cpp `
  --run-id whisper-demo
```

Continue individual stages:

```powershell
portpilot plan --run-directory runs\whisper-demo
portpilot status --run-directory runs\whisper-demo
portpilot report --run-directory runs\whisper-demo
portpilot execute --run-directory runs\whisper-demo --phase baseline
portpilot execute --run-directory runs\whisper-demo --phase target
```

Update a task through its guarded state machine:

```powershell
portpilot task `
  --run-directory runs\whisper-demo `
  --id prepare-target-build `
  --set-status in-progress
```

## Durable state

```text
runs/<run-id>/
  portpilot.yml
  project.json
  inventory.json
  dependencies.json
  findings.json
  architecture-decision.json
  task-graph.json
  tasks/
  results/
  evidence/
  report.json
```

JSON files are written through same-directory temporary files and atomically
replaced. A run lock prevents concurrent writers and complete status snapshots
also participate in the lock.

## Source gate

Before analysis, PortPilot verifies:

- The workspace is a Git checkout.
- `HEAD` equals the manifest's 40-character revision.
- The working tree is clean.
- `origin` matches the manifest repository.

Failure marks analysis and the project failed. PortPilot does not silently scan
or build a different source state.

## Stages and resumption

| Stage | Behavior |
|---|---|
| Analysis | Runs H2 skills and writes validated inventory, dependency, finding, and decision outputs |
| Planning | Groups findings by skill and writes validated task files plus an acyclic graph |
| Execution | Runs manifest tool probes, builds, parity checks, architecture checks, runtime scenarios, and optional package auditing |
| Reporting | Writes the current evidence, gate status, unresolved risks, and readiness verdict |

Re-running `portpilot run` skips completed analysis and planning stages and
regenerates the report. Failed stages may be retried after their underlying
problem is corrected.

## Task model

Every task records:

- Owner and skill
- Finding and file inputs
- Allowed file scope
- Dependencies
- Acceptance checks
- Attempt count
- State

The initial `prepare-target-build` task is ready. Finding tasks depend on it,
and final target validation depends on every remediation task. A task cannot
enter `in-progress` until all dependencies are done.

Task IDs are schema-validated before filesystem access. Any task update
invalidates the existing report so stale readiness evidence cannot be mistaken
for current state.

Execution details and evidence paths are documented in
[PortPilot Execution Adapters](PORTPILOT_EXECUTION_ADAPTERS.md). Native target
execution and clean-install isolation are supplied by the H5 CI pipeline.
