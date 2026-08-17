# Building PortPilot

PortPilot should be built as a **hybrid system**: reusable skills encode
deterministic Windows-on-Arm porting knowledge, while specialized agents plan,
execute, review, and iterate. The skills are the project's long-term knowledge
base; the agents are the workflow engine that applies and improves it.

## Core workflow

```text
Repository URL/path
  -> baseline run with plain Copilot
  -> repository inventory and compatibility scan
  -> Arm64 vs Arm64EC architecture decision
  -> migration plan and task graph
  -> skill/agent-driven changes
  -> x64 and Arm build
  -> functional, architecture, and performance validation
  -> independent adversarial review
  -> MSIX/MSI packaging
  -> evidence bundle and reusable skill extraction
```

The project meeting recommends starting **without skills or MCPs**, recording
where Copilot fails, and creating skills only for demonstrated gaps. This gives
the hackathon a measurable before-and-after story rather than merely presenting
a prebuilt agent.

## Route 1: AI skills

A skill is a focused, reusable porting procedure containing detection rules,
decision guidance, implementation instructions, scripts, examples, and
acceptance checks. It should solve one recurring class of problem rather than
attempt an entire port.

Qualcomm's [EasyWoS](https://github.com/qualcomm/EasyWoS) provides a strong
model for this route:

```text
static scan
  -> normalize findings
  -> match each finding to a specification
  -> dispatch it to a leaf skill
  -> generate a change
  -> build and verify
  -> improve the skill when output is inadequate
```

Its skill tree includes baseline porting, build enablement, SSE/AVX-to-NEON
conversion, x64 assembly conversion, Arm64EC JIT handling, profiling,
reporting, and a top-level orchestrator skill. PortPilot can adopt this pattern
without copying the whole EasyWoS web application.

### Skill contract

Each skill should define:

| Field | Purpose |
|---|---|
| Trigger | Scanner finding, build diagnostic, file pattern, or explicit invocation |
| Preconditions | Language, build system, target ABI, toolchain, and required hardware |
| Inputs | Relevant files, scan item, architecture decision, and build logs |
| Procedure | Exact analysis and transformation steps |
| Constraints | Forbidden shortcuts and behavior that must remain unchanged |
| Verification | Build command, tests, binary inspection, and expected evidence |
| Outputs | Patch, structured result, logs, and remediation status |
| Escalation | Conditions requiring another skill or a human decision |

### Initial skill set

| Skill | Responsibility |
|---|---|
| `repository-profiler` | Detect languages, build systems, binaries, tests, packaging, and native dependencies |
| `architecture-selector` | Choose native Arm64, Arm64EC, or temporary x64 emulation and record the rationale |
| `compatibility-scanner` | Detect x86 intrinsics, assembly, architecture guards, binary-only dependencies, JIT assumptions, and build exclusions |
| `cmake-arm64-enablement` | Add Arm64 and Arm64EC presets or toolchain configuration |
| `msbuild-arm64-enablement` | Add solution/platform configurations and correct dependency linkage |
| `sse-avx-to-neon` | Replace or isolate x86 SIMD while preserving semantics |
| `x64-asm-to-arm64` | Port assembly or select portable intrinsic/library alternatives |
| `dependency-remediation` | Upgrade, rebuild, replace, isolate, or retain x64 dependencies under Arm64EC |
| `architecture-verifier` | Inspect PE headers and prove the artifact is actually Arm64 or Arm64EC |
| `feature-parity` | Generate and execute before-and-after scenarios |
| `performance-baseline` | Compare startup, CPU, memory, power, and representative workloads |
| `windows-packaging` | Produce architecture-correct MSIX/MSI artifacts and installation checks |
| `porting-report` | Assemble decisions, patches, test results, benchmarks, and remaining risks |

### Skill execution model

Use a machine-readable finding such as:

```json
{
  "id": "PP-0042",
  "category": "x86-simd",
  "file": "src/codec.cpp",
  "symbol": "decode_block",
  "target": "arm64",
  "evidence": "_mm256_loadu_si256",
  "status": "open"
}
```

The dispatcher maps `x86-simd` to the SIMD skill. The skill must produce a
patch and verification result, not just advice. If the patch builds but fails
behavioral tests, the workflow fixes the **skill or specification** and reruns
it.

This is the crucial EasyWoS principle: do not let the orchestrator silently
hand-write a one-off fix, because that teaches PortPilot nothing reusable.

### Strengths and limitations

The skill route is reproducible, inspectable, inexpensive to rerun, and ideal
for known patterns. It is weaker at ambiguous repository-wide decisions,
cross-cutting failures, and coordinating dependent changes.

A skill-only MVP can expose one top-level `port-to-windows-arm` workflow, but
internally it should still dispatch work to narrow leaf skills.

## Route 2: Multi-agent system

The internal architecture documents define an orchestrator that writes little
code itself. It analyzes the repository, creates a migration plan and task
graph, delegates work, tracks dependencies, combines results, and enforces
validation gates.

| Agent | Inputs | Main output |
|---|---|---|
| Orchestrator | Repository, target, policies, and prior evidence | Project profile, architecture decision, task DAG, and status |
| Dependency agent | Source, manifests, binaries, and scan findings | Dependency graph and remediation plan |
| Implementation agent | Approved tasks and relevant skills | Focused patches and build fixes |
| UI agent | UI source and running application | DPI, theme, layout, input, and Windows UX fixes |
| Testing agent | Original behavior, tests, and ported build | Feature matrix, tests, and regression report |
| Performance agent | x64 baseline and Arm build | Startup, CPU, memory, and power comparisons |
| Review agent | Diff and evidence without implementer reasoning | Independent defects and accept/reject decision |
| Packaging agent | Approved binaries and metadata | MSIX/MSI, installation evidence, and release notes |

### Shared state

Agents should communicate through files and schemas rather than conversational
memory. A practical run directory is:

```text
runs/<run-id>/
  project.json
  architecture-decision.md
  inventory.json
  findings.json
  task-graph.json
  feature-matrix.yaml
  patches/
  builds/x64/
  builds/arm64/
  tests/results.json
  performance/results.json
  reviews/findings.json
  package/
  release-readiness.md
```

Every task should have an ID, owner, dependencies, allowed file scope, input
artifacts, acceptance checks, attempt count, and status. This enables
interruption, resumption, auditability, and safe parallelism.

### Orchestration behavior

1. **Intake:** Clone into an isolated worktree and record the commit, license,
   target architecture, supported features, and trusted build commands.
2. **Baseline:** Build and test the existing app on its supported architecture.
   Record failures rather than changing anything.
3. **Analysis:** Run repository profiling, static compatibility scans,
   dependency inspection, and binary inventory in parallel.
4. **Architecture decision:** Prefer native Arm64. Select Arm64EC only when an
   in-process x64 dependency or plugin prevents a complete native build.
5. **Planning:** Convert findings into a dependency-aware task DAG with explicit
   verification for every task.
6. **Implementation:** Assign bounded tasks to implementation agents, with each
   agent invoking the applicable skills. Avoid multiple agents editing the
   same files simultaneously.
7. **Integration:** Merge small reviewed changes, rebuild frequently, and feed
   compiler and test diagnostics into new tasks.
8. **Validation:** Run feature-parity, architecture, performance, and
   installation tests on Windows Arm hardware or an Azure Arm VM.
9. **Adversarial review:** Give separate reviewers the diff and acceptance
   criteria. Reviewers find defects; they do not implement. The implementation
   agent addresses accepted findings.
10. **Release:** Package only after all required gates pass, then archive the
    evidence and extract generally useful fixes into skills.

### Lessons from the Bun rewrite

The [Bun Rust rewrite](https://bun.com/blog/bun-in-rust) demonstrates that an
agentic transformation succeeds through controlled loops, not a single giant
prompt:

- Write the porting guide and architectural mappings before generating code.
- Trial the workflow on a few representative files before scaling.
- Preserve behavior and architecture first; defer broad refactoring.
- Use the existing language-independent test suite as the main oracle.
- Separate implementer and reviewer contexts. Bun used one implementer and at
  least two adversarial reviewers.
- Fix the workflow that produced a recurring defect instead of repeatedly
  patching individual outputs.
- Shard work carefully and isolate it with worktrees. Prohibit destructive Git
  commands and overlapping file ownership.
- Treat "compiles successfully" as insufficient. Several defects found by
  Bun's reviewers compiled cleanly.

### Strengths and limitations

Agents handle ambiguity, decomposition, feedback loops, and cross-cutting work
better than standalone skills. They also cost more, can conflict, and may drift
unless their tools, file ownership, state transitions, and gates are tightly
constrained.

## Windows-on-Arm architecture decisions

Microsoft's
[Windows on Arm overview](https://learn.microsoft.com/windows/arm/overview)
recommends native Arm64 for performance, responsiveness, and battery life.
Windows 11 can emulate x64, but emulation should be a baseline or fallback, not
evidence of a successful native port.

Use **native Arm64** when every in-process binary can be rebuilt for Arm64. Use
**Arm64EC** when incremental migration is necessary because the process still
loads x64 libraries or plugins.

Arm64EC code runs natively while x64 code runs under emulation in the same
process, but Arm64EC cannot link ordinary Arm64 libraries. The dependency agent
must therefore classify every DLL and LIB as x64, Arm64EC, Arm64, Arm64X, or
unavailable.

For C++ projects, Microsoft's
[Arm64EC build guide](https://learn.microsoft.com/windows/arm/arm64ec-build)
requires:

- Windows 11 SDK
- Visual Studio 2022 Arm64 tools
- An Arm64EC MSBuild platform or CMake architecture configuration
- `/arm64EC` compilation
- `/MACHINE:ARM64EC` linking

Final artifacts should be checked using `link /dump /headers`, not merely
trusted because a build configuration was named `Arm64EC`.

## Validation gates

The internal project documents emphasize evidence-based validation:

| Gate | Required evidence |
|---|---|
| Feature parity | Core scenarios work before and after the port |
| Test success | Automated tests pass on the target architecture |
| Architecture | x64 baseline and Arm64/Arm64EC binaries are verified |
| Performance | No unacceptable startup, CPU, memory, or power regression |
| Independent review | A separate agent approves the change or returns findings |
| Release readiness | Package installation, launch, upgrade, and uninstall succeed |

## Recommended repository structure

```text
PortPilot/
  README.md
  schemas/
  scanner/
  orchestrator/
  agents/
    dependency/
    implementation/
    ui/
    testing/
    performance/
    review/
    packaging/
  skills/
    repository-profiler/
    architecture-selector/
    cmake-arm64-enablement/
    msbuild-arm64-enablement/
    sse-avx-to-neon/
    x64-asm-to-arm64/
    architecture-verifier/
    windows-packaging/
  prompts/
  scripts/
  tests/
    fixtures/
    skills/
    orchestration/
  examples/<demo-app>/
  .github/workflows/
```

Keep the orchestration engine lightweight. For the hackathon, a CLI plus
JSON/YAML state, Markdown skill definitions, PowerShell/Node.js/Python helper
scripts, Git worktrees, and GitHub Actions or Azure Arm execution is enough. A
database and web dashboard should come later unless they directly improve the
demo.

## Delivery plan

| Phase | Deliverable |
|---|---|
| 1. Baseline | Candidate app, public proof of the Arm gap, plain-Copilot transcript, and x64 build/tests |
| 2. Vertical slice | Profiler, architecture selector, one build-enablement skill, one implementation agent, and Arm build |
| 3. Validation | Feature matrix, tests, PE architecture proof, and basic benchmark |
| 4. Agent expansion | Dependency, testing, review, performance, and packaging agents |
| 5. Reuse proof | Apply the same workflow to a second small repository or fixture |
| 6. Demo | Before-and-after comparison, installable package, and evidence report |

The best MVP is **not seven agents at once**. Build one complete vertical slice:

```text
orchestrator
  -> scanner
  -> architecture decision
  -> one or two leaf skills
  -> implementation
  -> build and test
  -> adversarial review
  -> package
```

Once that works, split responsibilities into additional agents. This preserves
the reusable-agent vision while ensuring the hackathon produces a working,
demonstrable port rather than only an architecture diagram.

## Project deliverables

The internal proposal and orchestration documents define these expected
deliverables:

1. A working Windows port of an open-source application.
2. A Windows Arm64 or Arm64EC build.
3. Feature-parity evidence.
4. Architecture evidence.
5. Test evidence.
6. Performance evidence.
7. Reusable Copilot agents.
8. Reusable skills.
9. A lightweight orchestrator.
10. Documentation for onboarding another repository.

## References

- [Hackathon 2026 project meeting recap](https://teams.microsoft.com/l/meetingrecap?driveId=b%21jd6evveiXU2ESRujmsNp1HrJAoleTQ1PvcX0gphuL20f-cM2Z9P7Sb7RtPEa24so&driveItemId=01N7IDLZFZG6VBLIKRSJA3DNZVTD7KUA2K&threadId=19%3Ameeting_YzgyOWNkODYtNjkxZi00ZDcyLTk1OTgtY2MyMjE2NzNlZmYz%40thread.v2&iCalUid=040000008200E00074C5B7101A82E00807EA08070303638B4823DD010000000000000000100000009D10C8BB0A1BA049BD92465364A12CCB)
- [MultiAgent Porting Orchestration](https://microsofteur-my.sharepoint.com/personal/t-lsingoei_microsoft_com/_layouts/15/Doc.aspx?sourcedoc=%7B680D380B-36AE-4C5C-A0B2-D5A9F2C2E09C%7D&file=MultiAgent_Porting_Orchestration.docx&action=default&mobileredirect=true&DefaultItemOpen=1)
- [Windows App Porting Proposal](https://microsofteur-my.sharepoint.com/personal/t-leengari_microsoft_com/_layouts/15/Doc.aspx?sourcedoc=%7BDD6ADCB0-AB1B-4869-AF31-F3D43B03BA80%7D&file=WINDOWS%20APP%20PORTING%20PROPOSAL.docx&action=default&mobileredirect=true&DefaultItemOpen=1)
- [Rewriting Bun in Rust](https://bun.com/blog/bun-in-rust)
- [Windows on Arm documentation](https://learn.microsoft.com/windows/arm/overview)
- [Arm64EC overview](https://learn.microsoft.com/windows/arm/arm64ec)
- [Get started with Arm64EC](https://learn.microsoft.com/windows/arm/arm64ec-build)
- [Qualcomm EasyWoS](https://github.com/qualcomm/EasyWoS)
