# PocketSphinx Windows Arm64 Porting Process

## Objective

Produce and validate a native Windows Arm64 PocketSphinx build and Python wheel
while developing reusable PortPilot skills, agent contracts, and evidence.

Target repository: [cmusphinx/pocketsphinx](https://github.com/cmusphinx/pocketsphinx)

Public gap: [Windows ARM64 - PocketSphinx issue #487](https://github.com/cmusphinx/pocketsphinx/issues/487)

Pinned starting revision:
`511126b492dcb267cf30d49d631946d7b61a9530` (PocketSphinx 5.1.1).

## Principles

1. Preserve upstream behavior before refactoring.
2. Make the smallest independently verifiable change at each milestone.
3. Record failures before fixing them.
4. Prefer native Arm64. Use Arm64EC only if an unavoidable in-process x64
   dependency is discovered.
5. Keep implementer and reviewer responsibilities separate.
6. Convert recurring fixes into PortPilot skills instead of retaining one-off
   instructions.
7. Do not claim Arm64 support until the binary architecture and execution on a
   Windows Arm64 machine are verified.

## Definition of done

The pilot is complete when:

- PocketSphinx builds from the pinned source on Windows Arm64.
- Its C tests pass on Windows Arm64.
- A `win_arm64` Python wheel is produced.
- The wheel installs into native Windows Arm64 Python without compiling.
- Python tests and a speech-recognition smoke test pass.
- PE headers prove that native modules are Arm64.
- The build is repeatable in CI.
- The port includes build, test, performance, and packaging evidence.
- At least one reusable PortPilot skill is extracted and tested.

## Milestone flow

```text
M0 Candidate lock
  -> M1 x64 baseline
  -> M2 Arm64 discovery
  -> M3 native C build
  -> M4 C validation
  -> M5 Python wheel
  -> M6 Arm64 runtime validation
  -> M7 CI and release integration
  -> M8 PortPilot reuse and demo
```

Each milestone must satisfy its exit gate before the next milestone begins.
Failures create findings and tasks; they do not get hidden by changing the
acceptance criteria.

## M0 - Candidate lock and reproducibility

### Work

- Pin the upstream commit and record repository/license metadata.
- Capture issue #487 and the maintainer response as evidence of the gap.
- Create an isolated working clone or worktree outside the PortPilot source.
- Record host architecture and installed tool versions.
- Define trusted commands before changing upstream source.

### Outputs

- `runs/<run-id>/project.json`
- `runs/<run-id>/environment.json`
- `runs/<run-id>/source.json`
- Clean source checksum and Git status

### Exit gate

- The exact source revision can be restored.
- The working tree is clean.
- Required commands and expected artifacts are documented.

## M1 - Unmodified Windows x64 baseline

### Work

Install only the prerequisites required by the upstream build:

- Python 3.12 or 3.13 x64
- CMake 3.25 or newer
- Visual Studio 2022 C++ build tools
- Windows SDK
- Ninja if selected as the CMake generator

Run the unmodified C build:

```powershell
cmake -S . -B build-x64 -A x64 -DBUILD_TESTING=ON
cmake --build build-x64 --config Release
ctest --test-dir build-x64 -C Release --output-on-failure
```

Run the unmodified Python build:

```powershell
py -3.12 -m venv .venv-x64
.\.venv-x64\Scripts\python -m pip install --upgrade pip
.\.venv-x64\Scripts\python -m pip install .
.\.venv-x64\Scripts\python -m pip install pytest memory_profiler
.\.venv-x64\Scripts\python -m pytest
```

Run one deterministic recognition input from the repository test data and save
its output for later comparison.

### Outputs

- Configure and build logs
- CTest and pytest results
- x64 wheel metadata
- Baseline recognition output
- Baseline executable/module PE headers
- Build duration and artifact sizes

### Exit gate

- The upstream x64 C build succeeds.
- Existing C and Python tests pass, or pre-existing failures are documented.
- A deterministic recognition result is captured.

## M2 - Arm64 discovery and architecture decision

### Work

The analysis agent inspects:

- CMake and scikit-build configuration
- GitHub Actions test and release matrices
- Compiler and architecture conditionals
- Intrinsics, inline assembly, and endian assumptions
- Generated Cython code
- Native Python and audio dependencies
- Wheel tags and packaging configuration

Attempt an unmodified Arm64 configure/build on a Windows Arm64 runner or VM:

```powershell
cmake -S . -B build-arm64 -A ARM64 -DBUILD_TESTING=ON
cmake --build build-arm64 --config Release
```

The first failure is evidence. Do not modify source until it is recorded and
classified.

### Finding schema

```json
{
  "id": "PS-ARM64-001",
  "category": "build-system",
  "file": "path/to/file",
  "evidence": "Exact diagnostic or source construct",
  "impact": "What this blocks",
  "proposedSkill": "cmake-windows-arm64",
  "status": "open"
}
```

### Architecture decision

Select native Arm64 unless a loaded dependency is available only as x64.
PocketSphinx is expected to be a native Arm64 candidate because its core is
portable C and its build system already supports multiple Arm platforms.

### Outputs

- Repository inventory
- Dependency and binary architecture matrix
- Structured findings
- Native Arm64 versus Arm64EC decision record
- Ordered remediation task graph

### Exit gate

- Every blocking failure has an owner, category, and verification command.
- The architecture choice is justified with dependency evidence.

## M3 - First native Arm64 C build

### Work

Apply only the changes required to configure and compile the core C library and
CLI for Arm64.

Likely change surfaces include:

- CMake generator/platform handling
- Architecture-safe compiler checks
- Windows type-size assumptions
- Release workflow matrix
- Architecture-specific output names

Every implementation task should invoke or create a focused PortPilot skill.

### Change rules

- One concern per commit.
- No unrelated cleanup.
- Preserve x64 behavior.
- Add a regression check for every discovered build-system defect.
- Do not disable warnings or tests to obtain a green build.

### Outputs

- Arm64 C library and CLI
- Focused patch series
- Build logs
- Initial `cmake-windows-arm64` skill

### Exit gate

- The C library and CLI compile successfully for Arm64.
- x64 still configures and builds.
- `dumpbin /headers` or `link /dump /headers` reports Arm64 for final binaries.

## M4 - Native C validation

### Work

- Run the complete CTest suite on Windows Arm64.
- Run CLI help and configuration smoke tests.
- Run recognition against the M1 audio fixture.
- Compare normalized output with the x64 baseline.
- Run an independent adversarial review of the diff.

The reviewer receives the source diff, diagnostics, and acceptance criteria,
but not the implementer's reasoning.

### Outputs

- Arm64 CTest report
- Feature-parity comparison
- Reviewer findings
- Fix-and-rerun evidence

### Exit gate

- All required C tests pass.
- Recognition behavior is equivalent within defined tolerances.
- No high-confidence review finding remains unresolved.

### Validation record

Native Windows Arm64 validation succeeded in
[public workflow run 32111597495](https://github.com/Kalunge/portpilot-pocketsphinx-arm64-validation/actions/runs/32111597495):

- 96 of 105 CTest entries passed.
- The nine failures are all present in the documented x64 Windows baseline:
  `test-main.sh`, `test_vad`, `test_lm_read`, `test_lm_score`,
  `test_lm_add`, `test_lm_class`, `test_lm_set`, `test_lm_write`, and
  `test_fopen`.
- No unexpected Arm64-specific test failure occurred.
- `pocketsphinx.exe` reports PE machine type `0xAA64`.
- Deterministic CLI recognition matched the x64 baseline.

## M5 - Native Python wheel

### Work

- Build with native Windows Arm64 Python.
- Ensure scikit-build-core selects the Arm64 CMake platform.
- Generate an architecture-correct `win_arm64` wheel.
- Audit bundled `.pyd` and DLL files.
- Avoid silently using an x64 Python interpreter or x64 build tool.

Expected command shape:

```powershell
python -m pip wheel . --no-deps --wheel-dir dist
python -m pip debug --verbose
```

### Outputs

- `pocketsphinx-<version>-<python>-<abi>-win_arm64.whl`
- Wheel contents and tag report
- PE architecture report for native wheel components
- Reusable `python-native-wheel-arm64` skill

### Exit gate

- The wheel tag is `win_arm64`.
- Every native binary in the wheel is Arm64.
- Installation does not invoke a local compiler.

### Validation record

[Public workflow run 32112092764](https://github.com/Kalunge/portpilot-pocketsphinx-arm64-validation/actions/runs/32112092764)
built `pocketsphinx-5.1.1-cp312-cp312-win_arm64.whl` with native Python
3.12. The wheel audit found
`pocketsphinx/_pocketsphinx.cp312-win_arm64.pyd` and verified its PE machine
type as `0xAA64`. The wheel was then installed into a newly created virtual
environment without building from source.

## M6 - Arm64 Python runtime validation

### Work

- Install the wheel into a clean native Arm64 Python environment.
- Run Python tests.
- Import the module and report process/module architecture.
- Run file-based recognition.
- Run a microphone demo if the VM/device exposes an audio input.
- Compare startup time, recognition time, memory, and artifact size with x64.

### Outputs

- Clean-install transcript
- pytest report
- Recognition output
- Architecture proof
- Basic performance comparison

### Exit gate

- Native import and tests pass.
- The speech demo works.
- Any regression outside the agreed threshold is investigated or documented.

### Validation record

The clean environment in
[workflow run 32112092764](https://github.com/Kalunge/portpilot-pocketsphinx-arm64-validation/actions/runs/32112092764)
successfully imported the installed native module. All 43 Python tests passed
in 16.15 seconds, and file-based recognition returned
`go forward ten meters`. The runner has no microphone input, so microphone
validation is not applicable. Comparative performance measurement remains an
M8 evidence task and is not a functional release blocker.

## M7 - CI, packaging, and release integration

### Work

- Add a Windows Arm64 test job using an available Arm64 runner.
- Add Windows Arm64 wheel production to the release workflow.
- Upload test logs and architecture reports as CI artifacts.
- Test installation from the built wheel in a fresh job.
- Document runner prerequisites and current GitHub runner limitations.

Issue #487 notes that GitHub Windows Arm64 runner behavior may be part of the
problem. Separate product defects from runner defects and preserve diagnostics
for both.

### Outputs

- Repeatable Arm64 CI job
- Release workflow update
- Install-and-run verification job
- Runner troubleshooting guidance

### Exit gate

- A clean CI run produces and validates the Arm64 wheel without manual steps.

### Validation record

[Public workflow run 32114030689](https://github.com/Kalunge/portpilot-pocketsphinx-arm64-validation/actions/runs/32114030689)
separates production and consumption into two native Arm64 jobs. The producer
builds, audits, and uploads the wheel and evidence. The consumer starts from a
fresh runner state, downloads the artifact, installs it into a new virtual
environment, and executes the Python and recognition gates.

## M8 - PortPilot reuse and demo

### Work

- Convert the successful process into reusable PortPilot skills.
- Run the skills against a clean PocketSphinx checkout.
- Prove that the generated result reaches the same validation gates.
- Prepare the before-and-after demo and evidence report.

### Required skills

- `repository-profiler`
- `architecture-selector`
- `cmake-windows-arm64`
- `python-native-wheel-arm64`
- `pe-architecture-verifier`
- `feature-parity`
- `porting-report`

### Demo script

1. Show `pip install pocketsphinx` failing or lacking a native wheel on
   Windows Arm64.
2. Show PortPilot profiling the repository and producing structured findings.
3. Show the task graph and selected skills.
4. Show the native Arm64 build and architecture verification.
5. Install the generated wheel into clean native Arm64 Python.
6. Run speech recognition.
7. Display x64 versus Arm64 test and performance evidence.
8. Re-run the same skills against a clean checkout to prove reuse.

### Exit gate

- The port is reproducible from a clean checkout.
- The evidence report links every claim to a command output or artifact.
- At least one skill is demonstrated on a second fixture or repository.

### Validation record

Two reusable skills were extracted:

- `pe-architecture-verifier`
- `python-native-wheel-arm64`

The workflow uses both skills from a clean checkout. Before inspecting
PocketSphinx, it tests the PE verifier against an independent synthetic AMD64
fixture, including a negative ARM64 mismatch assertion. It then verifies the
native PocketSphinx executable and Python extension. Both jobs passed in
[workflow run 32114030689](https://github.com/Kalunge/portpilot-pocketsphinx-arm64-validation/actions/runs/32114030689).
The repeatable demonstration is documented in
[POCKETSPHINX_DEMO.md](POCKETSPHINX_DEMO.md).

## Agent responsibilities

| Agent | PocketSphinx responsibility |
|---|---|
| Orchestrator | Maintain milestone state, task dependencies, and gates |
| Dependency agent | Classify Python, Cython, audio, compiler, and wheel dependencies |
| Implementation agent | Make bounded CMake, source, CI, and packaging changes |
| Testing agent | Maintain x64/Arm64 feature parity and execute test matrices |
| Performance agent | Compare recognition time, startup, memory, and artifact size |
| Review agent | Find build, ABI, packaging, and behavioral defects independently |
| Packaging agent | Produce and validate the `win_arm64` wheel |

## Branch and commit strategy

Use one branch for the pilot and small commits aligned to gates:

```text
port/windows-arm64
  m1: record x64 baseline
  m2: add Arm64 build diagnostics
  m3: enable native Arm64 C build
  m4: validate C behavior
  m5: produce win_arm64 wheel
  m6: validate native Python runtime
  m7: add CI and release integration
```

Do not combine generated artifacts, source changes, and workflow changes in one
commit unless they are inseparable.

## Run state

Each execution should create:

```text
runs/<run-id>/
  project.json
  environment.json
  source.json
  architecture-decision.md
  inventory.json
  findings.json
  task-graph.json
  builds/x64/
  builds/arm64/
  tests/
  performance/
  reviews/
  wheels/
  release-readiness.md
```

Large binaries and logs should be stored as CI/session artifacts rather than
committed to PortPilot.

## Current status

- M0 process definition: complete.
- Pinned source revision: cloned at
  `511126b492dcb267cf30d49d631946d7b61a9530`.
- Public compatibility gap: confirmed.
- Local baseline toolchain: Python 3.12.10, CMake 4.4.2, Ninja 1.13.2,
  MSVC 19.51.36252.0, and Windows SDK 10.0.26100.0.
- M1 x64 C build: successful with the unmodified source.
- M1 C tests: 75 test executables build and 65 of 102 runnable CTest entries
  pass. Pre-existing Windows failures are recorded for missing POSIX APIs
  (`setenv`, `popen`, and `pclose`), POSIX command dependencies, path parsing,
  and two test timeouts. Test executables are intentionally excluded from the
  default build and must be built through the `check` target.
- M1 Python wheel: successfully built as
  `pocketsphinx-5.1.1-cp312-cp312-win_amd64.whl`.
- M1 Python tests: 42 passed and 1 skipped.
- M2 discovery: complete. See
  [PocketSphinx Arm64 findings](POCKETSPHINX_ARM64_FINDINGS.md).
- Architecture decision: native Arm64.
- M3 native Arm64 build: complete. The C library, seven CLI programs, and 78
  test executables cross-compile successfully with MSVC 19.51.36252.0.
- Architecture proof: `pocketsphinx.exe` has PE machine type `0xAA64`.
- First implementation slice: the three MSVC test programs that referenced
  POSIX APIs now build; the fixed `test_config` passes on x64.
- M4 native C validation: complete. The native runner passes 96 of 105 CTest
  entries; all nine failures match the documented x64 Windows baseline, with
  zero unexpected Arm64 failures.
- M5 native Python wheel: complete. The CI artifact is
  `pocketsphinx-5.1.1-cp312-cp312-win_arm64.whl`, and its native extension is
  verified as PE machine type `0xAA64`.
- M6 Arm64 Python runtime validation: functionally complete. A clean native
  environment installed the wheel, all 43 Python tests passed, and deterministic
  file recognition succeeded.
- M7 CI and release integration: complete. Wheel production and clean-install
  validation run as separate native Arm64 jobs with transferred artifacts.
- M8 PortPilot reuse and demo: complete. Two reusable skills are exercised from
  a clean checkout, and the PE verifier also passes an independent AMD64 fixture
  test.
- Latest successful evidence:
  [public workflow run 32114030689](https://github.com/Kalunge/portpilot-pocketsphinx-arm64-validation/actions/runs/32114030689).
