# whisper.cpp Windows Arm64 Proof

## Result

PortPilot's second application,
[ggml-org/whisper.cpp](https://github.com/ggml-org/whisper.cpp), builds and runs
natively on Windows Arm64 from pinned revision
`1fe009caeda75f69bc864d6370b10674e45a92bd`.

Public proof:
[GitHub Actions run 32389275726](https://github.com/Kalunge/portpilot-pocketsphinx-arm64-validation/actions/runs/32389275726).

The run used the same `.github/workflows/portpilot.yml` producer pipeline as
PocketSphinx. No whisper-specific workflow fork was added.

## Native evidence

| Gate | Result |
|---|---|
| x64 baseline | Passed |
| Native Arm64 configure and build | Passed with Visual Studio `ClangCL` and platform `ARM64` |
| CTest parity | Passed with zero failures |
| JFK transcription | Passed both normalized transcript assertions |
| `whisper-cli.exe` PE machine | `0xAA64` |
| `whisper.dll` PE machine | `0xAA64` |
| Source integrity | Passed before and after commands |
| Report test gate | `passed` |

The clean-install consumer was skipped because whisper.cpp's manifest does not
define a package artifact. Native executable and DLL evidence is retained in
the producer artifact.

## Findings resolved during the proof

### Complete-test model

The original manifest downloaded only `ggml-tiny.en.bin`. The pinned CTest
suite's `test-vad-full` also requires `ggml-base.en.bin`; without it, the test
dereferenced a failed model load and crashed. The manifest now supplies both
models with exact SHA-256 values:

- tiny.en:
  `921e4cf8686fdd993dcd081a5da5b6c365bfde1162e72b08d75ac75289920b1f`
- base.en:
  `a03779c86df3323075f5e796cb2ce5029f00ec8869eee3fdfb897afe36c6d002`

No test was disabled or allow-listed.

### Correct runtime oracle

`tests/en-0-ref.txt` contains a Columbia speech and is unrelated to
`samples/jfk.wav`. The deterministic scenario now checks two normalized JFK
phrases emitted by the pinned tiny.en model instead of comparing unrelated
content.

### Out-of-source native configuration

Top-level CMake configuration rewrote tracked
`bindings/javascript/package.json` even during native builds. Patch
`0001-limit-javascript-package-generation-to-emscripten.patch` limits that
generation to its actual Emscripten publishing path. Emscripten behavior is
preserved, while x64 and Arm64 native builds leave source state unchanged.

### Arm64 compiler selection

ggml explicitly rejects MSVC for its Arm CPU backend:

```text
MSVC is not supported for ARM, use clang
```

The target manifest therefore adds `-T ClangCL` only to the Arm64 configure
command. The x64 baseline remains on its default MSVC toolchain.

## Skill improvements

The reusable compatibility scanner now reports:

- explicit compiler restrictions involving ARM/ARM64 as high-severity compiler
  findings assigned to `cmake-windows-arm64`;
- `configure_file` operations that write from and to `CMAKE_SOURCE_DIR` as
  reproducibility findings assigned to `cmake-out-of-source`.

These rules are application-independent and run for future CMake candidates.

## Remaining review boundary

The generated report remains `not-ready` even though its test gate is
`passed`. Static analysis tasks for architecture-guarded x86, Arm, and optional
backend code still require disposition. H7 will harden finding precision and
review those tasks; PortPilot does not infer that every static finding is
resolved merely because the selected build path succeeds.

