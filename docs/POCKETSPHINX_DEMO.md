# PocketSphinx Windows Arm64 Demo

## Result

PortPilot produces a native PocketSphinx 5.1.1 Windows Arm64 build and Python
wheel from pinned upstream commit
`511126b492dcb267cf30d49d631946d7b61a9530`.

Public validation repository:
[Kalunge/portpilot-pocketsphinx-arm64-validation](https://github.com/Kalunge/portpilot-pocketsphinx-arm64-validation)

Latest release-grade run:
[32114030689](https://github.com/Kalunge/portpilot-pocketsphinx-arm64-validation/actions/runs/32114030689)

## Demo sequence

1. Show the upstream gap in
   [PocketSphinx issue 487](https://github.com/cmusphinx/pocketsphinx/issues/487).
2. Show the pinned source, architecture decision, and structured findings in
   [POCKETSPHINX_ARM64_FINDINGS.md](POCKETSPHINX_ARM64_FINDINGS.md).
3. Show the focused upstream patch in
   `patches/pocketsphinx/0001-msvc-test-portability.patch`.
4. Open run 32114030689 and show the native `windows-11-arm` producer job.
5. Download `pocketsphinx-windows-arm64-evidence` and show:
   - `pocketsphinx-5.1.1-cp312-cp312-win_arm64.whl`
   - `pocketsphinx.exe` machine type `0xAA64`
   - `_pocketsphinx.cp312-win_arm64.pyd` machine type `0xAA64`
   - 96 of 105 CTest entries passing with zero unexpected Arm64 failures
6. Show the independent clean-install consumer job:
   - fresh native Arm64 Python 3.12 virtual environment
   - normal wheel installation
   - 43 Python tests passing
   - recognition output `go forward ten meters`
7. Show the reusable `pe-architecture-verifier` and
   `python-native-wheel-arm64` skills used by CI.

## Evidence summary

| Gate | Result |
|---|---|
| Native C/CLI build | Passed |
| Executable architecture | ARM64, PE `0xAA64` |
| C test parity | 96/105 passed; 9 known x64 Windows failures |
| Unexpected Arm64 C failures | 0 |
| Wheel | `pocketsphinx-5.1.1-cp312-cp312-win_arm64.whl` |
| Python extension architecture | ARM64, PE `0xAA64` |
| Clean install | Passed in independent job |
| Python tests | 43 passed |
| Recognition | `go forward ten meters` |

The public harness is the repeatability proof. Large binaries and logs remain
GitHub Actions artifacts rather than source-controlled files.
