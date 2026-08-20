# PortPilot Hackathon Workplan

## Objective

Turn the completed PocketSphinx pilot into a reusable CLI-driven system that
can analyze, plan, build, validate, and report a Windows Arm64 port for a
second application without application-specific workflow edits.

## Scope

### In scope

- C and C++ projects using CMake
- Optional native Python wheels
- Native Arm64 and Arm64EC architecture selection
- GitHub Actions `windows-11-arm` execution
- x64 baseline and Arm64 test parity
- PE architecture verification
- Clean artifact installation
- Evidence-backed porting reports

### Deferred

- GUI or dashboard
- MSIX and MSI generation
- Arbitrary build-system support
- Automatic upstream pull-request submission
- Large agent swarms
- Production hosting

## Milestones

| Milestone | Work | Deliverables | Exit gate | Estimate |
|---|---|---|---|---|
| **H0 - Scope and candidate lock** | Confirm the MVP boundary and select a second application with a verified Arm64 gap | Candidate scorecard, pinned revision, gap evidence, feature scenarios | Candidate is reproducible, legally usable, and genuinely lacks native Arm64 support | 0.5 day |
| **H1 - Contracts and schemas** | Define the port manifest and durable run-state formats | `portpilot.yml`; project, inventory, finding, task, result, and report schemas; PocketSphinx reference manifest | PocketSphinx is fully described without hard-coded workflow values | 1 day |
| **H2 - Repository analysis skills** | Build repository profiling, compatibility scanning, dependency inventory, and architecture selection | Tested skills with JSON output and fixtures | Clean PocketSphinx and second-application checkouts produce useful structured findings | 1.5 days |
| **H3 - Planner and orchestrator** | Implement a thin milestone state machine and dependency-aware task plan | CLI commands for `analyze`, `plan`, `run`, `status`, and `report`; resumable run directory | Interrupted runs resume safely; every task has inputs, scope, dependencies, and acceptance checks | 1.5 days |
| **H4 - Build and validation adapters** | Generalize CMake configuration, toolchain probing, baseline parity, PE checking, wheel auditing, and runtime scenarios | Reusable build and test adapters; existing PE and wheel skills integrated | PocketSphinx passes through the generic adapters with no PocketSphinx logic in the engine | 2 days |
| **H5 - Reusable CI pipeline** | Convert the current workflow into manifest-driven producer and clean-install consumer jobs | Reusable GitHub Actions workflow, evidence artifact layout, and failure summary | A clean CI run takes only a repository reference and manifest and produces an auditable result | 1 day |
| **H6 - Second-application proof** | Run PortPilot on the locked candidate and convert manual fixes into skills | Arm64 patch, artifacts, tests, report, and recorded skill improvements | The second application builds and runs natively without a candidate-specific workflow fork | 2-3 days |
| **H7 - Review and reliability** | Add negative fixtures, command safety, timeout handling, baseline regression checks, and independent review | Test suite, review report, documented limitations, and recovery paths | No unresolved high-confidence correctness or demo-blocking issue remains | 1 day |
| **H8 - Hackathon demo package** | Prepare the story, diagrams, scripted demo, evidence pages, and recorded fallback | Five-to-seven-minute demo, architecture diagram, before/after report, and backup recording | A new viewer can understand the problem, automation, native proof, and reuse across two applications | 1-2 days |

Expected total: approximately 11-13 focused engineering days, compressible
through parallel work after H1.

## Execution order

```text
H0 -> H1 -> H2 -> H3 -> H4 -> H5 -> H6 -> H7 -> H8
                    H2 fixtures ------> H4
                    Demo assets can begin during H6
```

## Required evidence per application

- Pinned source revision and clean-checkout proof
- x64 baseline and known-failure list
- Architecture decision with dependency rationale
- Generated findings and task graph
- Focused patch set
- Native Arm64 PE `0xAA64` reports
- Test-parity results and deterministic runtime scenario
- Clean artifact installation in an independent job
- Final release-readiness report

## Hackathon acceptance criteria

1. A repository and `portpilot.yml` are the only application-specific inputs.
2. PocketSphinx still passes through the generalized workflow.
3. A second real application reaches native Arm64 without workflow duplication.
4. At least three skills are reused unchanged across both applications.
5. Every success claim links to CI output or an artifact.
6. The demo runs from a clean checkout and has a recorded fallback.
7. Remaining unsupported cases are reported honestly rather than hidden.

## Approved product decisions

- Initial focus: CMake projects and optional native Python packages.
- User experience: CLI first; no dashboard requirement.
- Primary execution environment: GitHub Actions `windows-11-arm`.
- Second application: selected only after H0 verifies a genuine Arm64 gap.
- Definition of hackathon-ready: the acceptance criteria in this document.

## Current status

- PocketSphinx reference pilot: complete.
- H0 scope and candidate lock: complete.
- Second application:
  [ggml-org/whisper.cpp](https://github.com/ggml-org/whisper.cpp) at
  `1fe009caeda75f69bc864d6370b10674e45a92bd`.
- Candidate evidence:
  [Second Application Candidate Lock](docs/SECOND_APP_CANDIDATE.md).
- H1 contracts and schemas: complete.
- Shared manifests:
  `manifests/pocketsphinx/portpilot.yml` and
  `manifests/whisper-cpp/portpilot.yml`.
- Contract reference:
  [PortPilot Contracts](docs/PORTPILOT_CONTRACTS.md).
- H2 repository analysis skills: complete.
- Analysis reference:
  [PortPilot Repository Analysis Skills](docs/PORTPILOT_ANALYSIS_SKILLS.md).
- Clean-checkout architecture decisions: native Arm64 for both PocketSphinx and
  whisper.cpp.
- H3 planner and orchestrator: complete.
- Orchestrator reference:
  [PortPilot Orchestrator](docs/PORTPILOT_ORCHESTRATOR.md).
- Clean-checkout runs for both projects produce resumable, dependency-aware
  plans and truthful `not-ready` reports before execution.
- H4 build and validation adapters: complete.
- Execution adapter reference:
  [PortPilot Execution Adapters](docs/PORTPILOT_EXECUTION_ADAPTERS.md).
- The generic PocketSphinx x64 baseline preserves its exact nine-failure
  Windows parity set and passes deterministic recognition.
- H5 reusable CI pipeline: complete.
- CI reference:
  [PortPilot Reusable CI](docs/PORTPILOT_CI.md).
- Public producer/consumer proof:
  [GitHub Actions run 32363364618](https://github.com/Kalunge/portpilot-pocketsphinx-arm64-validation/actions/runs/32363364618).
- H6 second-application proof: complete.
- whisper.cpp native proof:
  [Windows Arm64 proof](docs/WHISPER_CPP_ARM64_PROOF.md) and
  [GitHub Actions run 32389275726](https://github.com/Kalunge/portpilot-pocketsphinx-arm64-validation/actions/runs/32389275726).
- H7-H8: pending.
