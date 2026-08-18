---
name: python-native-wheel-arm64
description: Audit a Windows Arm64 Python wheel tag and verify every bundled PE binary is native Arm64.
---

# Python native wheel Arm64

Build with native Arm64 Python, audit with `Test-WheelArchitecture.ps1`, then
install the artifact into a fresh native Arm64 environment in a separate job.
Reject a non-`win_arm64` tag, an empty native payload, or any PE image other
than machine type `0xAA64`.
