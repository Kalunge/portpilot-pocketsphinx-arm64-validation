from __future__ import annotations

from pathlib import Path
from typing import Any

from portpilot.analysis.architecture_selector import select_architecture
from portpilot.analysis.common import load_manifest, write_json
from portpilot.analysis.compatibility_scanner import scan_repository
from portpilot.analysis.dependency_inventory import (
    inventory_dependencies,
    native_dependency_summary,
)
from portpilot.analysis.repository_profiler import profile_repository
from portpilot.contracts import validate_contract


def analyze(
    manifest_path: Path,
    repository: Path,
    output_directory: Path,
) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    project_id = manifest["project"]["id"]

    dependencies = inventory_dependencies(repository, project_id)
    inventory = profile_repository(
        repository,
        project_id,
        native_dependency_summary(dependencies),
    )
    findings = scan_repository(repository, project_id)
    decision = select_architecture(
        project_id,
        inventory,
        dependencies,
        findings,
    )

    validate_contract("dependency-inventory.schema.json", dependencies)
    validate_contract("inventory.schema.json", inventory)
    for finding in findings:
        validate_contract("finding.schema.json", finding)
    validate_contract("architecture-decision.schema.json", decision)

    outputs = {
        "dependencies.json": dependencies,
        "inventory.json": inventory,
        "findings.json": findings,
        "architecture-decision.json": decision,
    }
    for name, value in outputs.items():
        write_json(output_directory / name, value)
    return {
        "projectId": project_id,
        "dependencyCount": len(dependencies["dependencies"]),
        "findingCount": len(findings),
        "selectedArchitecture": decision["selectedArchitecture"],
        "outputs": sorted(outputs),
    }

