from __future__ import annotations

import re
from pathlib import Path
from typing import Any


TEMPLATE_PATTERN = re.compile(r"\$\{([^}]+)\}")


def cmake_value(value: str | bool | int | float) -> str:
    if isinstance(value, bool):
        return "ON" if value else "OFF"
    return str(value)


def template_values(manifest: dict[str, Any], phase: str) -> dict[str, str]:
    build = manifest["build"]
    variant = build["variants"][phase]
    values = {
        "phase": phase,
        "sourceDirectory": build["sourceDirectory"],
        "buildDirectory": build["buildDirectory"].replace("${phase}", phase),
        "platform": variant["platform"],
        "configuration": manifest["target"]["configuration"],
    }
    return values


def expand(value: str, variables: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in variables:
            raise ValueError(f"unknown template variable: {name}")
        return variables[name]

    return TEMPLATE_PATTERN.sub(replace, value)


def expand_command(
    command: dict[str, Any],
    manifest: dict[str, Any],
    phase: str,
    additional_variables: dict[str, str] | None = None,
) -> tuple[str, list[str], str | None]:
    variables = template_values(manifest, phase)
    variables.update(additional_variables or {})
    executable = expand(command["executable"], variables)
    arguments = [expand(value, variables) for value in command["arguments"]]
    if command.get("appendDefinitions"):
        arguments.extend(
            f"-D{name}={cmake_value(value)}"
            for name, value in sorted(manifest["build"]["definitions"].items())
        )
    working_directory = command.get("workingDirectory")
    if working_directory:
        working_directory = expand(working_directory, variables)
    return executable, arguments, working_directory


def contained_path(root: Path, value: str) -> Path:
    candidate = (root / value).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as error:
        raise ValueError(f"path escapes execution root: {value}") from error
    return candidate

