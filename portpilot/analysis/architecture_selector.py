from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .common import load_manifest, utc_now, write_json


def select_architecture(
    project_id: str,
    inventory: dict[str, Any],
    dependency_inventory: dict[str, Any],
    findings: list[dict[str, Any]],
) -> dict[str, Any]:
    x64_only_dependencies = [
        item["name"]
        for item in dependency_inventory["dependencies"]
        if set(item["architectures"]) <= {"x86", "x64"}
        and "x64" in item["architectures"]
        and item.get("inProcess") is True
    ]
    assembly_findings = [
        item["id"] for item in findings if item["category"] == "assembly"
    ]
    blocker_findings = [
        item["id"] for item in findings if item["severity"] == "blocker"
    ]

    evidence = [
        f"Detected build systems: {', '.join(inventory['buildSystems']) or 'none'}",
        f"Native dependencies inventoried: {len(inventory['nativeDependencies'])}",
        f"Compatibility findings: {len(findings)}",
    ]
    blockers = []
    if x64_only_dependencies:
        selected = "arm64ec"
        confidence = "high"
        blockers.extend(
            f"x64-only in-process dependency: {name}"
            for name in sorted(x64_only_dependencies)
        )
        rationale = (
            "Arm64EC is required because one or more in-process native "
            "dependencies are available only for x64."
        )
    else:
        selected = "arm64"
        confidence = "high" if inventory["buildSystems"] else "medium"
        rationale = (
            "Native Arm64 is preferred because no unavoidable x64-only "
            "in-process dependency was found."
        )

    if assembly_findings:
        evidence.append(
            "Assembly findings requiring architecture-selection review: "
            + ", ".join(assembly_findings)
        )
    if blocker_findings:
        blockers.extend(
            f"Compatibility blocker requiring remediation: {finding_id}"
            for finding_id in blocker_findings
        )
        selected = "blocked"
        confidence = "high"
        rationale = (
            "Architecture selection is blocked until unresolved blocker "
            "findings are remediated or shown to be unreachable for this target."
        )

    return {
        "projectId": project_id,
        "generatedAt": utc_now(),
        "selectedArchitecture": selected,
        "confidence": confidence,
        "rationale": rationale,
        "evidence": evidence,
        "blockers": blockers,
    }


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def main() -> int:
    parser = argparse.ArgumentParser(description="Select Windows Arm architecture.")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--dependencies", required=True, type=Path)
    parser.add_argument("--findings", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    decision = select_architecture(
        manifest["project"]["id"],
        load_json(args.inventory),
        load_json(args.dependencies),
        load_json(args.findings),
    )
    write_json(args.output, decision)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
