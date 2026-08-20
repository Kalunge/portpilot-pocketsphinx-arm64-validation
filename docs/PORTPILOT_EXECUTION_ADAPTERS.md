# PortPilot Execution Adapters

## Purpose

H4 binds a validated `portpilot.yml` to policy-constrained build and validation
execution. The engine contains no PocketSphinx-specific branches: commands,
paths, expected architectures, known test failures, runtime expectations, and
package rules all come from the manifest.

## Usage

Create the analyzed and planned run first:

```powershell
portpilot run `
  --manifest manifests\pocketsphinx\portpilot.yml `
  --repository C:\src\pocketsphinx `
  --runs-directory runs `
  --run-id pocketsphinx-demo
```

The checkout directory must match `source.checkoutDirectory`; this prevents a
manifest path from resolving to a different sibling checkout.

Execute the x64 baseline:

```powershell
portpilot execute `
  --run-directory runs\pocketsphinx-demo `
  --phase baseline
```

Execute and package on the native Arm64 runner:

```powershell
portpilot execute `
  --run-directory runs\pocketsphinx-demo `
  --phase target `
  --package
```

Runs with a package contract are complete only after baseline, target, and
package evidence exists. Runs without one complete after baseline and target.

## Execution policy

- Commands are executable-plus-argument arrays and never pass through a shell.
- PATH-resolved tools are restricted to `cmake`, `ctest`, `git`, `perl`, and
  `python`.
- Repository-produced executables and all working, result, and capture paths
  must remain inside their declared roots.
- Manifest PATH entries that exist are prepended; missing candidates are
  recorded. Tool probes fail execution if the required capability is absent.
- Every command has a timeout and writes separate stdout, stderr, and
  schema-validated result records.
- The pinned Git revision and origin are rechecked immediately before
  execution.
- Applied patch file hashes are recorded. A resumed run rejects changed source,
  undeclared tracked changes, and untracked files outside declared resources or
  build directories.

## Validation adapters

| Adapter | Gate |
|---|---|
| Resources | Download to a temporary file and accept only the declared SHA-256 |
| Patches | Apply with the declared strip level, verify assertions, and tolerate only an already-applied identical patch |
| CMake | Expand structured arguments and append deterministic sorted definitions |
| Test parity | Delete stale result files, parse current CTest failures, and reject failures outside the manifest allow-list |
| PE architecture | Read the COFF machine value and require the manifest architecture before target execution |
| Runtime scenario | Check exit code and normalized output or reference text |
| Python wheel | Require a `win_arm64` tag, at least one native PE file, and Arm64 machine type for every bundled PE |

## Evidence

Execution adds these records beneath the run directory:

```text
evidence/
  environment/<phase>-toolchain.json
  source/execution.json
  build/
  tests/<phase>-<suite>.json
  runtime/<phase>-<scenario>.json
  architecture.json
  package/wheel.json
  <phase>-summary.json
results/
  <phase>-<command>.json
```

## PocketSphinx reference result

The generic x64 baseline adapter configured and built pinned revision
`511126b492dcb267cf30d49d631946d7b61a9530`, retained exactly the nine approved
Windows failures, rejected no additional test, and passed deterministic file
recognition. Native target execution and clean installation remain CI work for
H5 because the development machine is x64.

