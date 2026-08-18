#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from portpilot.analysis.architecture_selector import select_architecture
from portpilot.analysis.common import load_manifest, write_json
from portpilot.analysis.compatibility_scanner import scan_repository
from portpilot.analysis.dependency_inventory import (
    inventory_dependencies,
    native_dependency_summary,
)
from portpilot.analysis.repository_profiler import profile_repository


SCHEMA_DIRECTORY = ROOT / "schemas"


def load_schema(name: str) -> dict[str, Any]:
    with (SCHEMA_DIRECTORY / name).open(encoding="utf-8") as stream:
        return json.load(stream)


def validate(name: str, value: Any) -> None:
    validator = Draft202012Validator(
        load_schema(name),
        format_checker=FormatChecker(),
    )
    errors = sorted(
        validator.iter_errors(value),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        messages = []
        for error in errors:
            location = ".".join(str(part) for part in error.absolute_path) or "<root>"
            messages.append(f"{name}: {location}: {error.message}")
        raise ValueError("\n".join(messages))


def analyze(manifest_path: Path, repository: Path, output_directory: Path) -> dict[str, Any]:
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

    validate("dependency-inventory.schema.json", dependencies)
    validate("inventory.schema.json", inventory)
    for finding in findings:
        validate("finding.schema.json", finding)
    validate("architecture-decision.schema.json", decision)

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


def main() -> int:
    parser = argparse.ArgumentParser(description="Run PortPilot repository analysis.")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--repository", required=True, type=Path)
    parser.add_argument("--output-directory", required=True, type=Path)
    args = parser.parse_args()

    repository = args.repository.resolve()
    if not repository.is_dir():
        parser.error(f"repository does not exist: {repository}")
    summary = analyze(
        args.manifest.resolve(),
        repository,
        args.output_directory.resolve(),
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
