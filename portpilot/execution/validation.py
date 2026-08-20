from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from portpilot.analysis.common import write_json
from portpilot.execution.templates import contained_path, expand, template_values


MACHINE_TYPES = {
    "ARM64": 0xAA64,
    "ARM64EC": 0xA641,
    "AMD64": 0x8664,
    "X86": 0x014C,
}


def read_pe_machine(path: Path) -> int:
    with path.open("rb") as stream:
        if stream.read(2) != b"MZ":
            raise ValueError(f"{path} is not a PE image")
        stream.seek(0x3C)
        offset_bytes = stream.read(4)
        if len(offset_bytes) != 4:
            raise ValueError(f"{path} has an invalid PE offset")
        stream.seek(int.from_bytes(offset_bytes, "little"))
        if stream.read(4) != b"PE\0\0":
            raise ValueError(f"{path} has an invalid PE signature")
        machine = stream.read(2)
        if len(machine) != 2:
            raise ValueError(f"{path} has no PE machine value")
        return int.from_bytes(machine, "little")


def verify_architecture(
    manifest: dict[str, Any],
    execution_root: Path,
    run_directory: Path,
) -> dict[str, Any]:
    configuration = manifest["validation"]["architecture"]
    expected_name = configuration["expectedMachine"]
    expected = MACHINE_TYPES[expected_name]
    files = []
    for value in configuration["files"]:
        path = contained_path(execution_root, value)
        machine = read_pe_machine(path)
        files.append(
            {
                "path": value.replace("\\", "/"),
                "machine": f"0x{machine:04X}",
                "expected": f"0x{expected:04X}",
                "matches": machine == expected,
            }
        )
    report = {"expectedMachine": expected_name, "files": files}
    write_json(run_directory / "evidence" / "architecture.json", report)
    mismatches = [item for item in files if not item["matches"]]
    if mismatches:
        raise RuntimeError(f"architecture mismatch: {json.dumps(mismatches)}")
    return report


def parse_failed_tests(path: Path) -> list[str]:
    if not path.is_file():
        return []
    failures = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = re.fullmatch(r"\s*\d+:(.+?)\s*", line)
        if match:
            failures.append(match.group(1))
    return sorted(set(failures))


def evaluate_test_suite(
    suite: dict[str, Any],
    phase: str,
    manifest: dict[str, Any],
    execution_root: Path,
    run_directory: Path,
    command_result: dict[str, Any],
) -> dict[str, Any]:
    variables = template_values(manifest, phase)
    result_path = contained_path(
        execution_root,
        expand(suite.get("resultPath", ""), variables),
    )
    failed = parse_failed_tests(result_path)
    known = sorted(set(suite.get("knownFailures", [])))
    unexpected = sorted(set(failed) - set(known))
    policy = suite["failurePolicy"]
    passed = (
        not failed
        if policy == "all-pass"
        else not unexpected
        if policy in {"no-new-failures", "allow-listed"}
        else False
    )
    if command_result["outcome"] == "expected-failure" and not failed:
        passed = False
        unexpected = ["test command failed without a parseable failure list"]
    report = {
        "id": suite["id"],
        "phase": phase,
        "policy": policy,
        "commandOutcome": command_result["outcome"],
        "failed": failed,
        "knownFailures": known,
        "unexpectedFailures": unexpected,
        "passed": passed,
    }
    write_json(
        run_directory / "evidence" / "tests" / f"{phase}-{suite['id']}.json",
        report,
    )
    if not passed:
        raise RuntimeError(
            f"{phase} suite {suite['id']} has unexpected failures: "
            f"{', '.join(unexpected or failed)}"
        )
    return report


def normalize_output(value: str, operations: list[str]) -> str:
    for operation in operations:
        if operation == "strip-timestamps":
            value = re.sub(r"\[[^\]]+\]", " ", value)
        elif operation == "trim":
            value = value.strip()
        elif operation == "lowercase":
            value = value.lower()
        elif operation == "collapse-whitespace":
            value = " ".join(value.split())
    return value


def evaluate_scenario(
    scenario: dict[str, Any],
    phase: str,
    execution_root: Path,
    run_directory: Path,
    command_result: dict[str, Any],
) -> dict[str, Any]:
    stdout = run_directory / command_result["stdoutPath"]
    actual = stdout.read_text(encoding="utf-8", errors="replace")
    expected = scenario["expected"]
    operations = expected.get("normalization", [])
    normalized = normalize_output(actual, operations)
    failures = []
    if command_result["exitCode"] != expected["exitCode"]:
        failures.append(
            f"exit code {command_result['exitCode']} != {expected['exitCode']}"
        )
    for fragment in expected.get("outputContains", []):
        expected_fragment = normalize_output(fragment, operations)
        if expected_fragment not in normalized:
            failures.append(f"output does not contain {fragment!r}")
    reference = expected.get("referenceFile")
    reference_match = None
    if reference:
        reference_value = contained_path(execution_root, reference).read_text(
            encoding="utf-8",
            errors="replace",
        )
        normalized_reference = normalize_output(reference_value, operations)
        reference_match = normalized_reference in normalized
        if not reference_match:
            failures.append(f"output does not contain reference file {reference}")
    report = {
        "id": scenario["id"],
        "phase": phase,
        "exitCode": command_result["exitCode"],
        "referenceMatch": reference_match,
        "failures": failures,
        "passed": not failures,
    }
    write_json(
        run_directory / "evidence" / "runtime" / f"{phase}-{scenario['id']}.json",
        report,
    )
    if failures:
        raise RuntimeError(f"{phase} scenario {scenario['id']}: {'; '.join(failures)}")
    return report


def audit_wheel(
    wheel: Path,
    run_directory: Path,
    package: dict[str, Any],
    expected_name: str = "ARM64",
) -> dict[str, Any]:
    platform_tag = package["platformTag"]
    if not wheel.name.endswith(f"-{platform_tag}.whl"):
        raise RuntimeError(f"wheel has incorrect platform tag: {wheel.name}")
    expected = MACHINE_TYPES[expected_name]
    native_files = []
    with zipfile.ZipFile(wheel) as archive:
        for name in archive.namelist():
            if not name.lower().endswith((".pyd", ".dll", ".exe")):
                continue
            data = archive.read(name)
            if data[:2] != b"MZ":
                raise RuntimeError(f"{name} is not a PE image")
            offset = int.from_bytes(data[0x3C:0x40], "little")
            if data[offset : offset + 4] != b"PE\0\0":
                raise RuntimeError(f"{name} has an invalid PE signature")
            machine = int.from_bytes(data[offset + 4 : offset + 6], "little")
            native_files.append(
                {
                    "path": name,
                    "machine": f"0x{machine:04X}",
                    "matches": machine == expected,
                }
            )
    if not native_files:
        raise RuntimeError("wheel contains no native PE files")
    missing_patterns = [
        pattern
        for pattern in package["nativeFiles"]
        if not any(
            PurePosixPath(item["path"]).match(pattern.replace("\\", "/"))
            for item in native_files
        )
    ]
    if missing_patterns:
        raise RuntimeError(
            "wheel is missing required native files: " + ", ".join(missing_patterns)
        )
    report = {
        "wheel": wheel.name,
        "platformTag": platform_tag,
        "nativeFiles": native_files,
    }
    write_json(run_directory / "evidence" / "package" / "wheel.json", report)
    if any(not item["matches"] for item in native_files):
        raise RuntimeError("wheel contains a non-Arm64 native binary")
    return report
