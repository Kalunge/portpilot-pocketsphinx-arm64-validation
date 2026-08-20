from __future__ import annotations

import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from typing import Any

from portpilot.analysis.common import write_json
from portpilot.contracts import validate_contract
from portpilot.execution.templates import contained_path, expand, expand_command


ALLOWED_PATH_EXECUTABLES = {"cmake", "ctest", "git", "perl", "python"}


def timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def resolve_executable(
    execution_root: Path,
    executable: str,
    environment: dict[str, str] | None = None,
) -> str:
    if "/" in executable or "\\" in executable:
        path = contained_path(execution_root, executable)
        if not path.is_file():
            raise ValueError(f"executable does not exist: {executable}")
        return str(path)
    if executable.lower() not in ALLOWED_PATH_EXECUTABLES:
        raise ValueError(f"executable is not allow-listed: {executable}")
    resolved = shutil.which(executable, path=(environment or os.environ).get("PATH"))
    if not resolved:
        raise ValueError(f"executable is unavailable: {executable}")
    return resolved


def command_environment(
    manifest: dict[str, Any],
    command: dict[str, Any],
) -> tuple[dict[str, str], list[str], list[str]]:
    environment = os.environ.copy()
    path_entries = manifest.get("toolchain", {}).get("pathEntries", [])
    active_entries = [entry for entry in path_entries if Path(entry).is_dir()]
    missing_entries = [entry for entry in path_entries if entry not in active_entries]
    if active_entries:
        environment["PATH"] = os.pathsep.join(
            [*active_entries, environment.get("PATH", "")]
        )
    environment.update(command.get("environment", {}))
    return environment, active_entries, missing_entries


def execute_command(
    command: dict[str, Any],
    manifest: dict[str, Any],
    phase: str,
    execution_root: Path,
    run_directory: Path,
    task_id: str,
    additional_variables: dict[str, str] | None = None,
) -> dict[str, Any]:
    execution_root = execution_root.resolve()
    run_directory = run_directory.resolve()
    executable, arguments, working_directory = expand_command(
        command,
        manifest,
        phase,
        additional_variables,
    )
    environment, _, _ = command_environment(manifest, command)
    executable = resolve_executable(execution_root, executable, environment)
    cwd = (
        contained_path(execution_root, working_directory)
        if working_directory
        else execution_root
    )
    if not cwd.is_dir():
        raise ValueError(f"working directory does not exist: {cwd}")

    capture_template = command.get(
        "capture",
        f"evidence/commands/{phase}-{command['id']}.txt",
    )
    variables = {
        "phase": phase,
        **(additional_variables or {}),
    }
    capture_relative = expand(capture_template, variables)
    capture_path = contained_path(run_directory, capture_relative)
    capture_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path = capture_path.with_suffix(capture_path.suffix + ".stderr")

    started_at = timestamp()
    started = monotonic()
    outcome = "failure"
    exit_code = -1
    try:
        with (
            capture_path.open("w", encoding="utf-8", newline="\n") as stdout,
            stderr_path.open("w", encoding="utf-8", newline="\n") as stderr,
        ):
            completed = subprocess.run(
                [executable, *arguments],
                cwd=cwd,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                check=False,
                timeout=command.get("timeoutMinutes", 30) * 60,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        exit_code = completed.returncode
        if exit_code == 0:
            outcome = "success"
        elif command.get("continueOnError"):
            outcome = "expected-failure"
        else:
            outcome = "failure"
    except subprocess.TimeoutExpired:
        outcome = "timeout"
        exit_code = 124

    result = {
        "taskId": task_id,
        "commandId": command["id"],
        "phase": phase,
        "startedAt": started_at,
        "finishedAt": timestamp(),
        "exitCode": exit_code,
        "outcome": outcome,
        "stdoutPath": str(capture_path.relative_to(run_directory)).replace("\\", "/"),
        "stderrPath": str(stderr_path.relative_to(run_directory)).replace("\\", "/"),
        "artifacts": [],
        "metrics": {"durationSeconds": monotonic() - started},
    }
    validate_contract("result.schema.json", result)
    result_path = run_directory / "results" / f"{phase}-{command['id']}.json"
    write_json(result_path, result)
    if outcome in {"failure", "timeout"}:
        raise RuntimeError(
            f"{phase} command {command['id']} {outcome} with exit code {exit_code}"
        )
    return result
