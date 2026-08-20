from __future__ import annotations

from pathlib import Path
from typing import Any

from portpilot.analysis.common import read_json, write_json
from portpilot.contracts import validate_contract


def load_tasks(run_directory: Path) -> list[dict[str, Any]]:
    return [
        read_json(path)
        for path in sorted((run_directory / "tasks").glob("*.json"))
    ]


def create_report(run_directory: Path) -> dict[str, Any]:
    project = read_json(run_directory / "project.json")
    decision = read_json(run_directory / "architecture-decision.json")
    findings = read_json(run_directory / "findings.json")
    tasks = load_tasks(run_directory)

    unfinished = [task for task in tasks if task["status"] != "done"]
    failed = [
        task for task in tasks if task["status"] in {"blocked", "failed"}
    ]
    implementation_status = (
        "passed"
        if tasks and not unfinished
        else "blocked"
        if failed
        else "not-applicable"
    )
    architecture_status = (
        "blocked"
        if decision["selectedArchitecture"] == "blocked"
        else "passed"
    )
    evidence = [
        path.name
        for path in (
            run_directory / "inventory.json",
            run_directory / "dependencies.json",
            run_directory / "findings.json",
            run_directory / "architecture-decision.json",
            run_directory / "task-graph.json",
        )
        if path.is_file()
    ]
    report = {
        "runId": project["runId"],
        "projectId": project["projectId"],
        "sourceRevision": project["source"]["revision"],
        "targetArchitecture": project["target"]["architecture"],
        "architectureDecision": decision["rationale"],
        "summary": {
            "findings": len(findings),
            "tasks": len(tasks),
            "tests": 0,
            "unexpectedFailures": 0,
        },
        "gates": [
            {
                "id": "analysis",
                "status": (
                    "passed"
                    if project["stages"]["analysis"] == "done"
                    else "failed"
                ),
                "evidence": [
                    "inventory.json",
                    "dependencies.json",
                    "findings.json",
                ],
            },
            {
                "id": "architecture",
                "status": architecture_status,
                "evidence": ["architecture-decision.json"],
            },
            {
                "id": "planning",
                "status": (
                    "passed"
                    if project["stages"]["planning"] == "done"
                    else "not-applicable"
                ),
                "evidence": ["task-graph.json"] if tasks else [],
            },
            {
                "id": "implementation",
                "status": implementation_status,
                "evidence": [f"tasks/{task['id']}.json" for task in tasks],
            },
            {
                "id": "tests",
                "status": "not-applicable",
                "evidence": [],
            },
        ],
        "evidence": evidence,
        "remainingRisks": [
            f"{task['id']}: {task['title']}" for task in unfinished
        ],
        "verdict": (
            "ready"
            if tasks and not unfinished and architecture_status == "passed"
            else "not-ready"
        ),
    }
    validate_contract("report.schema.json", report)
    write_json(run_directory / "report.json", report)
    return report

