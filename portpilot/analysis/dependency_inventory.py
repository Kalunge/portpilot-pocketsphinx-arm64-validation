from __future__ import annotations

import argparse
import re
import tomllib
from pathlib import Path
from typing import Any

from .common import (
    iter_repository_files,
    load_manifest,
    read_text,
    relative_path,
    utc_now,
    write_json,
)


FIND_PACKAGE = re.compile(r"\bfind_package\s*\(\s*([A-Za-z0-9_.+-]+)", re.IGNORECASE)
FETCH_CONTENT = re.compile(
    r"\bFetchContent_Declare\s*\(\s*([A-Za-z0-9_.+-]+)",
    re.IGNORECASE,
)
ADD_SUBDIRECTORY = re.compile(
    r"\badd_subdirectory\s*\(\s*[\"']?([^\"')\s]+)",
    re.IGNORECASE,
)


def dependency(
    name: str,
    kind: str,
    source: str,
    evidence: str,
    architectures: list[str] | None = None,
    role: str = "unknown",
    in_process: bool | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "kind": kind,
        "source": source,
        "evidence": evidence,
        "role": role,
        "inProcess": in_process,
        "architectures": architectures or ["unknown"],
    }


def cmake_dependencies(repository: Path) -> list[dict[str, Any]]:
    results = []
    for path in iter_repository_files(repository):
        if path.name != "CMakeLists.txt" and path.suffix.lower() != ".cmake":
            continue
        text = read_text(path)
        if text is None:
            continue
        source = relative_path(repository, path)
        for match in FIND_PACKAGE.finditer(text):
            results.append(
                dependency(
                    match.group(1),
                    "cmake-package",
                    source,
                    match.group(0),
                )
            )
        for match in FETCH_CONTENT.finditer(text):
            results.append(
                dependency(
                    match.group(1),
                    "cmake-fetch",
                    source,
                    match.group(0),
                )
            )
        for match in ADD_SUBDIRECTORY.finditer(text):
            directory = match.group(1)
            if "${" in directory:
                continue
            candidate = (path.parent / directory).resolve()
            candidate_cmake = candidate / "CMakeLists.txt"
            candidate_text = (
                read_text(candidate_cmake) if candidate_cmake.is_file() else None
            )
            if (
                candidate.is_dir()
                and candidate.is_relative_to(repository.resolve())
                and candidate_text
                and re.search(r"\bproject\s*\(", candidate_text, re.IGNORECASE)
            ):
                results.append(
                    dependency(
                        Path(directory).name,
                        "bundled",
                        source,
                        match.group(0),
                    )
                )
    return results


def python_dependencies(repository: Path) -> list[dict[str, Any]]:
    results = []
    pyproject = repository / "pyproject.toml"
    if pyproject.is_file():
        with pyproject.open("rb") as stream:
            document = tomllib.load(stream)
        dependencies = document.get("project", {}).get("dependencies", [])
        for value in dependencies:
            name = re.split(r"[\s<>=!~;\[]", value, maxsplit=1)[0]
            if name:
                results.append(
                    dependency(name, "python", "pyproject.toml", value)
                )

    requirements = repository / "requirements.txt"
    if requirements.is_file():
        for line in requirements.read_text(encoding="utf-8").splitlines():
            value = line.strip()
            if not value or value.startswith(("#", "-")):
                continue
            name = re.split(r"[\s<>=!~;\[]", value, maxsplit=1)[0]
            results.append(
                dependency(name, "python", "requirements.txt", value)
            )
    return results


def vcpkg_dependencies(repository: Path) -> list[dict[str, Any]]:
    manifest_path = repository / "vcpkg.json"
    if not manifest_path.is_file():
        return []
    import json

    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    results = []
    for value in document.get("dependencies", []):
        name = value if isinstance(value, str) else value.get("name")
        if name:
            results.append(
                dependency(name, "vcpkg", "vcpkg.json", str(value))
            )
    return results


def inventory_dependencies(repository: Path, project_id: str) -> dict[str, Any]:
    discovered = (
        cmake_dependencies(repository)
        + python_dependencies(repository)
        + vcpkg_dependencies(repository)
    )
    unique = {}
    for item in discovered:
        key = (item["name"].lower(), item["kind"])
        unique.setdefault(key, item)
    return {
        "projectId": project_id,
        "generatedAt": utc_now(),
        "dependencies": sorted(
            unique.values(),
            key=lambda item: (item["name"].lower(), item["kind"], item["source"]),
        ),
    }


def native_dependency_summary(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "name": item["name"],
            "source": item["source"],
            "architectures": item["architectures"],
        }
        for item in inventory["dependencies"]
        if item["kind"] in {"cmake-package", "cmake-fetch", "bundled", "vcpkg"}
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Inventory repository dependencies.")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--repository", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    result = inventory_dependencies(
        args.repository.resolve(),
        manifest["project"]["id"],
    )
    write_json(args.output, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
