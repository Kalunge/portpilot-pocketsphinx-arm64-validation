from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml


EXCLUDED_DIRECTORIES = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "dist",
    "node_modules",
    "wheelhouse",
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def load_manifest(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        manifest = yaml.safe_load(stream)
    if not isinstance(manifest, dict):
        raise ValueError(f"{path} must contain a YAML object")
    return manifest


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=False)
        stream.write("\n")


def iter_repository_files(repository: Path) -> Iterator[Path]:
    for path in repository.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        relative = path.relative_to(repository)
        if any(
            part in EXCLUDED_DIRECTORIES or part.lower().startswith("build-")
            for part in relative.parts[:-1]
        ):
            continue
        yield path


def relative_path(repository: Path, path: Path) -> str:
    return str(path.relative_to(repository)).replace("\\", "/")


def read_text(path: Path, maximum_bytes: int = 2_000_000) -> str | None:
    try:
        if path.stat().st_size > maximum_bytes:
            return None
        return path.read_text(encoding="utf-8", errors="strict")
    except (UnicodeDecodeError, OSError):
        return None


def pe_machine(path: Path) -> str:
    machine_names = {
        0x014C: "x86",
        0x8664: "x64",
        0xAA64: "arm64",
        0xA641: "arm64ec",
    }
    try:
        with path.open("rb") as stream:
            if stream.read(2) != b"MZ":
                return "not-pe"
            stream.seek(0x3C)
            pe_offset_bytes = stream.read(4)
            if len(pe_offset_bytes) != 4:
                return "not-pe"
            pe_offset = int.from_bytes(pe_offset_bytes, "little")
            stream.seek(pe_offset)
            if stream.read(4) != b"PE\0\0":
                return "not-pe"
            machine_bytes = stream.read(2)
            if len(machine_bytes) != 2:
                return "not-pe"
            return machine_names.get(int.from_bytes(machine_bytes, "little"), "unknown")
    except OSError:
        return "unknown"
