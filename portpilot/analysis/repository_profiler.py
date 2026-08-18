from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from typing import Any

from .common import (
    iter_repository_files,
    load_manifest,
    pe_machine,
    relative_path,
    utc_now,
    write_json,
)


LANGUAGES = {
    ".asm": "Assembly",
    ".c": "C",
    ".cc": "C++",
    ".cpp": "C++",
    ".cxx": "C++",
    ".cs": "C#",
    ".h": "C/C++ Header",
    ".hh": "C/C++ Header",
    ".hpp": "C/C++ Header",
    ".java": "Java",
    ".js": "JavaScript",
    ".m": "Objective-C",
    ".mm": "Objective-C++",
    ".ps1": "PowerShell",
    ".py": "Python",
    ".rs": "Rust",
    ".s": "Assembly",
    ".swift": "Swift",
    ".ts": "TypeScript",
    ".zig": "Zig",
}

BUILD_MARKERS = {
    "CMakeLists.txt": "cmake",
    "Cargo.toml": "cargo",
    "Makefile": "make",
    "meson.build": "meson",
    "package.json": "npm",
    "pyproject.toml": "python",
    "setup.py": "setuptools",
}

PACKAGE_MARKERS = {
    "Cargo.lock": "cargo",
    "package-lock.json": "npm",
    "packages.lock.json": "nuget",
    "poetry.lock": "poetry",
    "pyproject.toml": "python",
    "requirements.txt": "pip",
    "vcpkg.json": "vcpkg",
}

BINARY_KINDS = {
    ".dll": "dll",
    ".exe": "exe",
    ".lib": "lib",
    ".pyd": "pyd",
}


def profile_repository(
    repository: Path,
    project_id: str,
    native_dependencies: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    languages: Counter[str] = Counter()
    build_systems: set[str] = set()
    package_systems: set[str] = set()
    binaries = []

    for path in iter_repository_files(repository):
        language = LANGUAGES.get(path.suffix.lower())
        if language:
            languages[language] += 1
        if path.name in BUILD_MARKERS:
            build_systems.add(BUILD_MARKERS[path.name])
        if path.name in PACKAGE_MARKERS:
            package_systems.add(PACKAGE_MARKERS[path.name])
        kind = BINARY_KINDS.get(path.suffix.lower())
        if kind:
            binaries.append(
                {
                    "path": relative_path(repository, path),
                    "kind": kind,
                    "machine": "unknown" if kind == "lib" else pe_machine(path),
                }
            )

    return {
        "projectId": project_id,
        "generatedAt": utc_now(),
        "languages": [
            {"name": name, "fileCount": count}
            for name, count in sorted(languages.items())
        ],
        "buildSystems": sorted(build_systems),
        "packageSystems": sorted(package_systems),
        "nativeDependencies": native_dependencies or [],
        "binaryFiles": sorted(binaries, key=lambda item: item["path"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Profile a source repository.")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--repository", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    result = profile_repository(args.repository.resolve(), manifest["project"]["id"])
    write_json(args.output, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
