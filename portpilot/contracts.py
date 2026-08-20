from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIRECTORY = ROOT / "schemas"


def load_schema(name: str) -> dict[str, Any]:
    with (SCHEMA_DIRECTORY / name).open(encoding="utf-8") as stream:
        return json.load(stream)


def validate_contract(name: str, value: Any) -> None:
    validator = Draft202012Validator(
        load_schema(name),
        format_checker=FormatChecker(),
    )
    errors = sorted(
        validator.iter_errors(value),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if not errors:
        return

    messages = []
    for error in errors:
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        messages.append(f"{name}: {location}: {error.message}")
    raise ValueError("\n".join(messages))

