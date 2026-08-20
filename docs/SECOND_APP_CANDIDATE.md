# Second Application Candidate Lock

## Decision

PortPilot's second application is
[ggml-org/whisper.cpp](https://github.com/ggml-org/whisper.cpp), pinned to:

```text
1fe009caeda75f69bc864d6370b10674e45a92bd
```

The pinned source identifies itself as version 1.9.2 and is licensed under the
MIT License.

## Selection criteria

The candidate must:

1. Have a verified current Windows Arm64 support gap.
2. Be publicly available under a usable open-source license.
3. Use CMake and native C or C++ so existing PortPilot skills apply.
4. Build and demonstrate within two to three focused days.
5. Include automated tests or a deterministic runtime scenario.
6. Be active and reproducible from a pinned revision.
7. Provide a visibly compelling hackathon demonstration.

## Scorecard

| Criterion | whisper.cpp | PortAudio | libsndfile |
|---|---:|---:|---:|
| Usable license | 5 - MIT | 5 - permissive | 3 - LGPL-2.1 |
| Verified Windows Arm64 gap | 5 | 4 | 4 |
| C/C++ and CMake fit | 5 | 5 | 5 |
| Deterministic automated validation | 5 | 3 | 4 |
| PocketSphinx skill reuse | 5 | 3 | 3 |
| Project activity | 5 | 3 | 3 |
| Hackathon demo impact | 5 | 2 | 2 |
| Delivery risk | 4 | 3 | 4 |
| **Total / 40** | **39** | **28** | **28** |

## Verified Windows Arm64 gap

Evidence checked on 2026-08-18:

- The current
  [Windows release matrix](https://github.com/ggml-org/whisper.cpp/blob/1fe009caeda75f69bc864d6370b10674e45a92bd/.github/workflows/release.yml)
  contains `Win32` and `x64`, but no Windows `ARM64` entry.
- The
  [Windows build workflow](https://github.com/ggml-org/whisper.cpp/blob/1fe009caeda75f69bc864d6370b10674e45a92bd/.github/workflows/build-windows.yml)
  uses only `ucrt-x86_64` and `clang-x86_64`.
- The
  [v1.9.2 release](https://github.com/ggml-org/whisper.cpp/releases/tag/v1.9.2)
  publishes Windows Win32 and x64 archives but no Windows Arm64 archive.
- [Issue 2132](https://github.com/ggml-org/whisper.cpp/issues/2132),
  "Version for Windows on Arm?", remains open.
- [Issue 512](https://github.com/ggml-org/whisper.cpp/issues/512),
  "Not working on Windows 11 Pro ARM64", remains open.

The repository does publish a Linux Arm64 artifact. The gap is therefore
specifically Windows Arm64 rather than general Arm portability.

## Reproducibility record

| Field | Value |
|---|---|
| Repository | `https://github.com/ggml-org/whisper.cpp` |
| Default branch | `master` |
| Pinned commit | `1fe009caeda75f69bc864d6370b10674e45a92bd` |
| Version | 1.9.2 |
| License | MIT |
| Build system | CMake |
| Languages | C and C++ |
| Native target | Windows Arm64 |
| Expected primary executable | `whisper-cli.exe` |
| Deterministic input | `samples/jfk.wav` |
| Reference output | Normalized JFK transcript assertions in `portpilot.yml` |

The pinned repository contains CTest integration, native C/C++ tests, the JFK
audio fixture, and reference English transcripts.

## Proposed validation scenarios

### Baseline

1. Build the pinned source for Windows x64 without modifications.
2. Run CTest and record pre-existing failures.
3. Run `whisper-cli` with the tiny English model and `samples/jfk.wav`.
4. Save the normalized transcript, duration, and PE architecture.

### Native Arm64

1. Configure with the Visual Studio ARM64 platform and `GGML_NATIVE=OFF`.
2. Build the library, tests, and `whisper-cli`.
3. Verify every final `.exe` and `.dll` as PE machine type `0xAA64`.
4. Run CTest on a `windows-11-arm` runner.
5. Transcribe `samples/jfk.wav` with the same model.
6. Compare the normalized transcript with the pinned JFK assertions.
7. Compare native Arm64 execution time with x64 emulation if the runner permits
   both.

Expected configure shape:

```powershell
cmake -S . -B build-arm64 -A ARM64 -T ClangCL `
  -DGGML_NATIVE=OFF `
  -DWHISPER_BUILD_TESTS=ON `
  -DWHISPER_BUILD_EXAMPLES=ON
```

This command shape is validated by
[public run 32389275726](https://github.com/Kalunge/portpilot-pocketsphinx-arm64-validation/actions/runs/32389275726).

## Skill reuse target

At least these existing or planned skills must apply without
application-specific forks:

- `repository-profiler`
- `architecture-selector`
- `cmake-windows-arm64`
- `pe-architecture-verifier`
- `feature-parity`
- `porting-report`

The PocketSphinx and whisper.cpp pilots share an audio-to-text workload, CMake,
native Windows binaries, deterministic audio fixtures, and transcript parity.

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Model download is large and externally hosted | Slower or flaky CI | Pin the model URL and SHA-256; cache only after checksum verification |
| ggml contains Arm-specific optimized code | Compiler or runtime defects may appear | Start with `GGML_NATIVE=OFF`, inventory architecture guards, then enable safe Arm optimizations deliberately |
| The port may compile without source changes | Weak transformation story | Treat missing CI, packaging, architecture proof, and runtime validation as the verified release gap; report honestly if no core patch is needed |
| Transcript output may vary with model or options | Unstable parity gate | Pin model checksum and CLI arguments; normalize timestamps and compare transcript text |
| Native inference can exceed CI time limits | Demo instability | Use the tiny English model and short checked-in JFK sample |

## H0 exit decision

H0 is complete:

- The MVP scope remains CMake/native applications on Windows Arm64.
- whisper.cpp has a current, independently verified Windows Arm64 release gap.
- The MIT license is suitable for the pilot.
- The exact source revision is pinned.
- Automated tests and a deterministic runtime scenario exist.
- Risks and initial verification commands are documented.

H1 will express this candidate and PocketSphinx through the same generic
manifest and evidence schemas.
