---
name: python-native-wheel-arm64
description: Audit a Windows Arm64 Python wheel tag and verify every bundled PE binary is native Arm64.
---

# Python native wheel Arm64

Use this skill after building a native Python wheel with Windows Arm64 Python.
It checks both the platform tag and the actual machine type of bundled native
code.

## Preconditions

- The wheel was built from a trusted, pinned source revision.
- `pe-architecture-verifier` is available beside this skill.
- Build logs record the Python process architecture.

## Procedure

1. Build without resolving runtime dependencies:

   ```powershell
   python -m pip wheel . --no-deps --wheel-dir wheelhouse
   ```

2. Audit the wheel:

   ```powershell
   .\.github\skills\python-native-wheel-arm64\scripts\Test-WheelArchitecture.ps1 `
     -WheelPath wheelhouse\package-version-cp312-cp312-win_arm64.whl `
     -OutputPath evidence\wheel-architecture.json
   ```

3. Upload the wheel and JSON report together.
4. In a separate native Arm64 job, download and install the wheel into a new
   virtual environment, then run import, test, and representative workload
   checks.

## Constraints

- Reject wheels whose filename does not end in `win_arm64.whl`.
- Reject wheels with no `.pyd`, `.dll`, or `.exe` payload.
- Reject any bundled PE image whose machine type is not `0xAA64`.
- Do not install from the source tree during clean-install validation.
