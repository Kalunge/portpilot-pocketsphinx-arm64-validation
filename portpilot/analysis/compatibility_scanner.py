from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Pattern

from .common import (
    iter_repository_files,
    load_manifest,
    read_text,
    relative_path,
    write_json,
)


SOURCE_EXTENSIONS = {
    ".asm",
    ".c",
    ".cc",
    ".cmake",
    ".cpp",
    ".cxx",
    ".h",
    ".hh",
    ".hpp",
    ".inc",
    ".s",
    ".yml",
    ".yaml",
}


@dataclass(frozen=True)
class Rule:
    category: str
    severity: str
    pattern: Pattern[str]
    impact: str
    proposed_skill: str
    extensions: frozenset[str] = frozenset(SOURCE_EXTENSIONS)


RULES = (
    Rule(
        "x86-intrinsic",
        "medium",
        re.compile(r"\b(?:_mm(?:256|512)?_[A-Za-z0-9_]+|__m(?:128|256|512)[di]?)\b"),
        "x86 SIMD code requires architecture-dispatch review and may need a portable or Arm implementation.",
        "x86-simd-remediation",
        frozenset({".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".inc"}),
    ),
    Rule(
        "assembly",
        "high",
        re.compile(r"\b(?:__asm__?|asm)\s*(?:\(|\{)"),
        "Inline assembly requires guard and target review before an Arm64 build.",
        "x64-asm-to-arm64",
        frozenset({".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".inc"}),
    ),
    Rule(
        "architecture-guard",
        "medium",
        re.compile(
            r"\b(?:_M_IX86|_M_X64|__i386__|__x86_64__|__amd64__|CMAKE_SIZEOF_VOID_P)\b"
        ),
        "Architecture-specific conditional logic must include or intentionally exclude Arm64.",
        "architecture-guard-review",
    ),
    Rule(
        "build-system",
        "medium",
        re.compile(r"(?:[\\/]|^)(?:x64|amd64|x86_64)(?:[\\/]|$)", re.IGNORECASE),
        "A hard-coded x64 path or platform may prevent Arm64 configuration.",
        "cmake-windows-arm64",
    ),
    Rule(
        "compiler",
        "high",
        re.compile(
            r"(?:MSVC|Clang|GCC).*(?:not supported|unsupported).*(?:ARM|ARM64)"
            r"|(?:ARM|ARM64).*(?:requires?|use).*(?:Clang|GCC|MSVC)",
            re.IGNORECASE,
        ),
        "An explicit Arm compiler restriction requires a compatible target toolchain.",
        "cmake-windows-arm64",
        frozenset({".cmake"}),
    ),
    Rule(
        "build-system",
        "medium",
        re.compile(
            r"configure_file\s*\([^)]*\$\{CMAKE_SOURCE_DIR\}"
            r"[^)]*\$\{CMAKE_SOURCE_DIR\}",
            re.IGNORECASE,
        ),
        "CMake configuration writes into the source tree and can invalidate reproducible build state.",
        "cmake-out-of-source",
        frozenset({".cmake"}),
    ),
)


def finding_id(project_id: str, index: int) -> str:
    project = re.sub(r"[^A-Z0-9]+", "-", project_id.upper()).strip("-")
    return f"PP-{project}-{index:03d}"


def scan_repository(repository: Path, project_id: str) -> list[dict[str, object]]:
    findings = []
    for path in sorted(iter_repository_files(repository)):
        suffix = path.suffix.lower()
        relative = relative_path(repository, path)
        if suffix in {".asm", ".s"}:
            findings.append(
                {
                    "category": "assembly",
                    "severity": "high",
                    "path": relative,
                    "line": 1,
                    "evidence": f"Architecture-specific assembly source: {relative}",
                    "impact": "Assembly source requires architecture identification and build-selection review.",
                    "proposedSkill": "x64-asm-to-arm64",
                }
            )

        is_cmake_lists = path.name == "CMakeLists.txt"
        if suffix not in SOURCE_EXTENSIONS and not is_cmake_lists:
            continue
        text = read_text(path)
        if text is None:
            continue
        lines = text.splitlines()
        for rule in RULES:
            if suffix not in rule.extensions and not is_cmake_lists:
                continue
            for line_number, line in enumerate(lines, start=1):
                stripped = line.strip()
                if stripped.startswith(("//", "/*", "*")):
                    continue
                if rule.pattern.search(line):
                    findings.append(
                        {
                            "category": rule.category,
                            "severity": rule.severity,
                            "path": relative,
                            "line": line_number,
                            "evidence": line.strip()[:500],
                            "impact": rule.impact,
                            "proposedSkill": rule.proposed_skill,
                        }
                    )
                    break

    findings.extend(scan_windows_workflows(repository))
    for index, finding in enumerate(findings, start=1):
        finding["id"] = finding_id(project_id, index)
        finding["projectId"] = project_id
        finding["status"] = "open"
    return findings


def scan_windows_workflows(repository: Path) -> list[dict[str, object]]:
    workflow_directory = repository / ".github" / "workflows"
    if not workflow_directory.is_dir():
        return []
    findings = []
    for path in sorted(workflow_directory.glob("*.y*ml")):
        text = read_text(path)
        if text is None:
            continue
        lowered = text.lower()
        has_windows = "windows" in lowered
        has_x64 = any(value in lowered for value in ("x64", "x86_64", "amd64"))
        has_arm64 = any(
            value in lowered
            for value in ("windows-11-arm", "arm64-windows", "clangarm64")
        )
        if has_windows and has_x64 and not has_arm64:
            findings.append(
                {
                    "category": "packaging",
                    "severity": "medium",
                    "path": relative_path(repository, path),
                    "line": 1,
                    "evidence": "Windows workflow contains x64 targets but no Windows Arm64 runner or platform.",
                    "impact": "Windows Arm64 builds and release artifacts are not continuously produced.",
                    "proposedSkill": "windows-arm64-ci",
                }
            )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan Windows Arm compatibility.")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--repository", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    findings = scan_repository(
        args.repository.resolve(),
        manifest["project"]["id"],
    )
    write_json(args.output, findings)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
