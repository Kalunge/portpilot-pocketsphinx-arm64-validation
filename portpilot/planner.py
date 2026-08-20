from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from portpilot.analysis.common import read_json, utc_now, write_json
from portpilot.contracts import validate_contract


OWNER_BY_CATEGORY = {
    "dependency": "dependency",
    "packaging": "packaging",
    "test-infrastructure": "testing",
}


def build_task(
    task_id: str,
    title: str,
    owner: str,
    finding_ids: list[str],
    inputs: list[str],
    depends_on: list[str],
    allowed_paths: list[str],
    acceptance_checks: list[str],
    status: str,
    skill: str,
) -> dict[str, Any]:
    task = {
        "id": task_id,
        "title": title,
        "owner": owner,
        "findingIds": sorted(finding_ids),
        "inputs": sorted(set(inputs)),
        "dependsOn": sorted(depends_on),
        "allowedPaths": sorted(set(allowed_paths)),
        "skill": skill,
        "acceptanceChecks": acceptance_checks,
        "attempts": 0,
        "status": status,
    }
    validate_contract("task.schema.json", task)
    return task


def create_plan(run_directory: Path) -> dict[str, Any]:
    project = read_json(run_directory / "project.json")
    findings = read_json(run_directory / "findings.json")
    decision = read_json(run_directory / "architecture-decision.json")

    tasks = [
        build_task(
            "prepare-target-build",
            f"Prepare the {decision['selectedArchitecture']} target build",
            "implementation",
            [],
            [
                "portpilot.yml",
                "inventory.json",
                "dependencies.json",
                "architecture-decision.json",
            ],
            [],
            ["CMakeLists.txt", "cmake/**", ".github/workflows/**"],
            [
                "The target CMake platform configures from a clean checkout.",
                "The baseline configuration remains supported.",
            ],
            "ready" if decision["selectedArchitecture"] != "blocked" else "blocked",
            "cmake-windows-arm64",
        )
    ]

    grouped_findings: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for finding in findings:
        grouped_findings[finding.get("proposedSkill", "manual-review")].append(finding)

    remediation_ids = []
    for skill, group in sorted(grouped_findings.items()):
        task_id = f"resolve-{skill}"
        remediation_ids.append(task_id)
        categories = {finding["category"] for finding in group}
        owner = (
            OWNER_BY_CATEGORY[next(iter(categories))]
            if len(categories) == 1 and next(iter(categories)) in OWNER_BY_CATEGORY
            else "implementation"
        )
        tasks.append(
            build_task(
                task_id,
                f"Resolve findings assigned to {skill}",
                owner,
                [finding["id"] for finding in group],
                ["findings.json", "architecture-decision.json"],
                ["prepare-target-build"],
                [finding.get("path", "**") for finding in group],
                [
                    "Every linked finding is resolved, accepted, or documented as unreachable.",
                    "The focused change does not regress the x64 baseline.",
                    "The applicable skill verification passes.",
                ],
                "pending",
                skill,
            )
        )

    validation_dependencies = ["prepare-target-build", *remediation_ids]
    tasks.append(
        build_task(
            "validate-target",
            "Validate architecture and feature parity",
            "testing",
            [],
            ["portpilot.yml", "architecture-decision.json", "inventory.json"],
            validation_dependencies,
            ["**"],
            [
                "All required target binaries have the expected PE machine type.",
                "No target test failure exists beyond the approved baseline.",
                "Every deterministic runtime scenario passes.",
            ],
            "pending",
            "feature-parity",
        )
    )

    assert_acyclic(tasks)
    graph = {
        "projectId": project["projectId"],
        "generatedAt": utc_now(),
        "tasks": [
            {"id": task["id"], "dependsOn": task["dependsOn"]} for task in tasks
        ],
    }
    validate_contract("task-graph.schema.json", graph)

    tasks_directory = run_directory / "tasks"
    tasks_directory.mkdir(exist_ok=True)
    for stale_task in tasks_directory.glob("*.json"):
        stale_task.unlink()
    for task in tasks:
        write_json(tasks_directory / f"{task['id']}.json", task)
    write_json(run_directory / "task-graph.json", graph)
    return graph


def assert_acyclic(tasks: list[dict[str, Any]]) -> None:
    dependencies = {task["id"]: set(task["dependsOn"]) for task in tasks}
    task_ids = set(dependencies)
    unknown = {
        dependency
        for values in dependencies.values()
        for dependency in values
        if dependency not in task_ids
    }
    if unknown:
        raise ValueError(f"task graph contains unknown dependencies: {sorted(unknown)}")

    ready = [task_id for task_id, values in dependencies.items() if not values]
    queued = set(ready)
    visited = set()
    while ready:
        task_id = ready.pop()
        queued.discard(task_id)
        visited.add(task_id)
        for candidate, values in dependencies.items():
            values.discard(task_id)
            if (
                not values
                and candidate not in visited
                and candidate not in queued
            ):
                ready.append(candidate)
                queued.add(candidate)
    if visited != task_ids:
        raise ValueError("task graph contains a dependency cycle")
