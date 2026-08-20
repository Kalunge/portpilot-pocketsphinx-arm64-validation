# PortPilot Reusable CI

## Purpose

H5 turns the manifest execution adapters into a reusable GitHub Actions
producer/consumer pipeline. Application-specific repository pins, runners,
dependencies, build commands, validations, artifacts, and package checks remain
in `portpilot.yml`; the workflow contains no PocketSphinx-specific build logic.

## Workflow

`.github/workflows/portpilot.yml` accepts one application input:
`manifest_path`, relative to the repository and ref containing the reusable
workflow.

```yaml
jobs:
  windows-arm:
    uses: owner/PortPilot/.github/workflows/portpilot.yml@ref
    with:
      manifest_path: manifests/my-project/portpilot.yml
```

The repository containing the reusable workflow must be readable by the caller.
PortPilot resolves that repository and its exact `github.workflow_sha`, then
checks the same immutable source into every job.

The workflow can also be dispatched directly with one of the reference
manifests.

## Jobs

| Job | Runner | Responsibility |
|---|---|---|
| `workflow-source` | `ubuntu-latest` | Resolve the reusable workflow repository and immutable commit |
| `metadata` | `ubuntu-latest` | Validate the manifest and expose runner, Python, package, and retention metadata |
| `baseline` | Manifest x64 runner | Install declared dependencies, create a pinned clean checkout, analyze, plan, and execute the baseline |
| `native-producer` | Manifest target runner | Download baseline state, rebind it to a new verified checkout, build and validate the native target, and optionally produce/audit a package |
| `clean-install-consumer` | Manifest target runner | Download producer artifacts into a fresh job, verify trusted state and source, install the package, and execute clean-install tests |

The consumer is skipped for manifests without a package contract.

## Trust boundaries

- Downloaded run state must contain the exact trusted manifest.
- Project ID, source URL, revision, checkout directory, and target architecture
  must match that manifest.
- Each runner uses a fresh checkout with the declared directory name, origin,
  pinned revision, and clean status.
- Cross-runner workspace paths are changed only through `portpilot rebind`.
- Package artifacts are rebuilt after stale matches are removed and audited
  before transfer and again before installation.
- The consumer executes only clean-install commands from the trusted workflow
  manifest, not producer-controlled state.
- Every job uses the workflow's immutable commit rather than a moving branch.

## Artifact layout

The producer uploads:

```text
portpilot-artifacts/
  artifact-index.json
  application/
    <manifest artifact paths>
  run/
    project.json
    portpilot.yml
    report.json
    evidence/
    results/
    tasks/
```

The clean consumer emits the same fixed layout with
`evidence/package/clean-install.json` and an updated final report. Job summaries
show the baseline, native, and clean-install JSON gates even when a previous
step fails.

## Reference proof

Public run
[32363364618](https://github.com/Kalunge/portpilot-pocketsphinx-arm64-validation/actions/runs/32363364618)
validated the manifest-driven PocketSphinx pipeline:

- x64 baseline completed with exactly the nine approved Windows CTest failures;
- native Arm64 build and deterministic recognition passed;
- PE and wheel audits verified Arm64 binaries;
- a `pocketsphinx-5.1.1-cp312-cp312-win_arm64.whl` artifact was produced;
- the independent Arm64 consumer passed all four clean-install commands.

The report test gate is `passed`. Its overall verdict remains `not-ready`
because H3 remediation tasks are still open; CI does not silently mark static
findings resolved merely because runtime gates pass.
