# PocketSphinx Windows Arm64 Findings

## Scope

Target: `cmusphinx/pocketsphinx` at
`511126b492dcb267cf30d49d631946d7b61a9530` (5.1.1).

This report records the M2 discovery results and the first M3 validation slice.

## Architecture decision

Use native Windows Arm64, not Arm64EC.

PocketSphinx is a portable C library with Cython bindings. Its architecture
header already recognizes `_M_ARM64` and `__aarch64__`, and the Windows SDK
contains native Arm64 system libraries. No in-process x64-only dependency was
found. Arm64EC would add ABI complexity without solving a dependency problem.

## Baseline evidence

- The unchanged x64 C library and CLI build successfully with MSVC.
- The Python 3.12 wheel builds as `win_amd64`.
- Python validation passes: 42 tests passed and 1 was skipped.
- The native C test target exposed pre-existing Windows portability defects.
  After excluding the three tests that did not link, 65 of 102 CTest entries
  passed.

## Findings

### PS-ARM64-001 - ARM64 compiler component is absent

```json
{
  "id": "PS-ARM64-001",
  "category": "environment",
  "file": "Visual Studio installation",
  "evidence": "CMake -A ARM64 fails while resolving VCTargetsPath for Platform='ARM64'; no Hostx64/arm64 cl.exe is installed.",
  "impact": "Blocks local native Arm64 compilation and PE verification.",
  "proposedSkill": "windows-arm64-toolchain-probe",
  "status": "resolved"
}
```

The Windows SDK 10.0.26100.0 Arm64 libraries and the Visual Studio ARM64 C++
compiler component are installed. CMake selects MSVC 19.51.36252.0 from
`Hostx64/arm64`.

### PS-ARM64-002 - MSVC test programs use POSIX names

```json
{
  "id": "PS-ARM64-002",
  "category": "test-portability",
  "file": "test/unit/test_config.c, test/unit/test_endpointer.c, test/unit/test_vad.c",
  "evidence": "MSVC link failures for setenv, popen, and pclose.",
  "impact": "The check target cannot build completely on Windows x64 or Arm64.",
  "proposedSkill": "msvc-posix-api-audit",
  "status": "fixed-in-pilot"
}
```

The pilot maps `setenv` to `_putenv_s` and `popen`/`pclose` to their MSVC
counterparts under `_WIN32`. All three targets then build, and `test_config`
passes on x64.

### PS-ARM64-003 - CTest assumes a POSIX runtime

```json
{
  "id": "PS-ARM64-003",
  "category": "test-infrastructure",
  "file": "test/CMakeLists.txt and shell-based tests",
  "evidence": "Windows tests require Bash, Perl modules, diff, SoX, and single-config executable paths.",
  "impact": "A native Windows runner cannot execute the complete suite without additional tools and path normalization.",
  "proposedSkill": "windows-ctest-dependency-audit",
  "status": "open"
}
```

The test executables are `EXCLUDE_FROM_ALL`; `cmake --build ... --target check`
must be used instead of building the default target before CTest.

### PS-ARM64-004 - Release automation omits Windows Arm64

```json
{
  "id": "PS-ARM64-004",
  "category": "packaging-ci",
  "file": ".github/workflows/release.yml and .github/workflows/tests.yml",
  "evidence": "The matrices include windows-latest but not windows-11-arm.",
  "impact": "No win_arm64 wheel is built or validated.",
  "proposedSkill": "python-native-wheel-arm64",
  "status": "open"
}
```

Upstream pull request 488 proposes adding `windows-11-arm` to the test and
release matrices, but does not address toolchain probing, native-binary
verification, or the Windows C test failures.

## First implementation slice

The isolated PocketSphinx checkout contains a three-file portability patch:

- `test_config.c`: use `_putenv_s` on Windows.
- `test_endpointer.c`: use `_popen` and `_pclose` on Windows.
- `test_vad.c`: use `_popen` and `_pclose` on Windows.

Validation:

```text
cmake --build build-x64 --config Release \
  --target test_config test_endpointer test_vad

Result: all three targets built successfully.

ctest --test-dir build-x64 -C Release -R ^test_config$

Result: 1/1 passed.
```

## Native Arm64 build evidence

The pinned source, with only the three-file MSVC test portability patch,
configures and builds successfully:

```text
cmake -S . -B build-arm64 -A ARM64 -DBUILD_TESTING=ON
cmake --build build-arm64 --config Release

Result: native C library and all seven CLI programs built successfully.
```

The generated `pocketsphinx.exe` PE header contains machine type `0xAA64`
(`ARM64`). Building the `check` target produces 78 Arm64 test executables.
CTest execution is intentionally deferred to a native Windows Arm64 host; an
x64 host cannot execute these binaries. The multi-configuration `check` target
also invokes CTest without `-C Release`, an independent upstream test-driver
defect that must be corrected before CI validation.

## Ordered remediation graph

1. Fix the multi-configuration `check` target to pass the selected build
   configuration to CTest.
2. Separate native tests from Bash/POSIX integration tests on Windows.
3. Add `windows-11-arm` test and release jobs.
4. Run the 78 native test executables on Windows Arm64.
5. Build a `win_arm64` wheel with native Arm64 Python.
6. Verify every `.exe`, `.dll`, and `.pyd` PE machine type before publishing.
