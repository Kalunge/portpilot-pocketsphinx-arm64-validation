# PortPilot
A reusable, agent-driven workflow that analyses, ports, tests, and packages open-source applications for Windows x64 and Arm64 — powered by GitHub Copilot.

## Tasks

### Research on how to implement a multi-agent

1. Research on how to implement a multi-agent.
2. Each of us should find an app not compatible with Arm requiring porting.
3. Thorough research on how porting has been done before, i.e. Bun.
4. Read articles — just proper, detailed research on the apps not compatible.

### Start with no skills, then see where the gaps are

1. Spin up an Azure VM (Arm).
2. Run Copilot in the VM and try to port an app from AMD64 to Arm64.
3. Test in the VM.
4. Document the entire process.
5. Use AI to improve the documentation.
6. Create an agent.

## Porting pilots

- [PocketSphinx incremental porting process](docs/POCKETSPHINX_PORTING_PROCESS.md)
- [PocketSphinx Arm64 findings and architecture decision](docs/POCKETSPHINX_ARM64_FINDINGS.md)
- [PocketSphinx Windows Arm64 demo](docs/POCKETSPHINX_DEMO.md)

## Reusable skills

- `pe-architecture-verifier`: validates `.exe`, `.dll`, and `.pyd` PE machine
  types and emits JSON evidence.
- `python-native-wheel-arm64`: verifies a `win_arm64` wheel tag and audits every
  bundled native binary.

## Hackathon productization

- [Approved workplan](plan.md)
- [Manifest and run-state contracts](docs/PORTPILOT_CONTRACTS.md)
- [Repository analysis skills](docs/PORTPILOT_ANALYSIS_SKILLS.md)
- [Resumable PortPilot orchestrator](docs/PORTPILOT_ORCHESTRATOR.md)
- [Second application candidate lock](docs/SECOND_APP_CANDIDATE.md)
