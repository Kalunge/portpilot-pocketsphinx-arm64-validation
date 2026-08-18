# PocketSphinx Windows Arm64 Validation

Public validation harness for the PortPilot PocketSphinx pilot.

The workflow checks out PocketSphinx 5.1.1 at
`511126b492dcb267cf30d49d631946d7b61a9530`, applies the Windows test
portability patch, and validates the build on GitHub's native
`windows-11-arm` runner.

Validation gates:

- native C library, CLI, and test build;
- CTest execution;
- PE machine type `0xAA64`;
- deterministic speech recognition;
- uploaded environment, test, architecture, and recognition evidence.
