from __future__ import annotations

import glob
from pathlib import Path
from typing import Any

from portpilot.analysis.common import load_manifest, read_json, write_json
from portpilot.execution.process import command_environment, execute_command
from portpilot.execution.source import (
    apply_patches,
    git_output,
    prepare_resources,
    verify_source_changes,
    verify_source_revision,
)
from portpilot.execution.validation import (
    audit_wheel,
    evaluate_scenario,
    evaluate_test_suite,
    verify_architecture,
)
from portpilot.execution.templates import contained_path, expand, template_values
from portpilot.state import RunState


PORTPILOT_ROOT = Path(__file__).resolve().parents[2]


def execution_root(state: RunState) -> Path:
    repository = Path(state.load_project()["source"]["workspace"]).resolve()
    return repository.parent


def execution_is_complete(state: RunState) -> bool:
    manifest = load_manifest(state.manifest_path)
    baseline_path = state.root / "evidence" / "baseline-summary.json"
    target_path = state.root / "evidence" / "target-summary.json"
    if not baseline_path.is_file() or not target_path.is_file():
        return False
    baseline = read_json(baseline_path)
    target = read_json(target_path)
    if not phase_summary_passed(baseline, "baseline", manifest):
        return False
    if not phase_summary_passed(target, "target", manifest):
        return False
    package_required = "package" in manifest["validation"]
    if not package_required:
        return True
    clean_install = state.root / "evidence" / "package" / "clean-install.json"
    return target.get("package") is not None and clean_install.is_file()


def phase_summary_passed(
    summary: dict[str, Any],
    phase: str,
    manifest: dict[str, Any],
) -> bool:
    if summary.get("phase") != phase:
        return False
    expected_probes = {
        probe["id"] for probe in manifest.get("toolchain", {}).get("probes", [])
    }
    probes = summary.get("environment", {}).get("probes", [])
    if {probe.get("id") for probe in probes} != expected_probes:
        return False
    if any(probe.get("outcome") != "success" for probe in probes):
        return False
    expected_builds = {
        command["id"]
        for command in manifest["build"]["commands"]
        if phase in command["phases"]
    }
    build_results = summary.get("buildResults", [])
    if {result.get("id") for result in build_results} != expected_builds:
        return False
    if any(result.get("outcome") != "success" for result in build_results):
        return False
    expected_suites = {
        suite["id"]
        for suite in manifest["validation"]["testSuites"]
        if phase in suite["phases"]
    }
    suites = summary.get("testSuites", [])
    if {suite.get("id") for suite in suites} != expected_suites:
        return False
    if any(not suite.get("passed") for suite in suites):
        return False
    expected_scenarios = {
        scenario["id"]
        for scenario in manifest["validation"]["scenarios"]
        if phase in scenario["phases"]
    }
    scenarios = summary.get("scenarios", [])
    if {scenario.get("id") for scenario in scenarios} != expected_scenarios:
        return False
    if any(not scenario.get("passed") for scenario in scenarios):
        return False
    if phase == "target":
        architecture = summary.get("architecture")
        files = architecture.get("files", []) if architecture else []
        expected_files = {
            value.replace("\\", "/")
            for value in manifest["validation"]["architecture"]["files"]
        }
        if {item.get("path") for item in files} != expected_files:
            return False
        if any(not item.get("matches") for item in files):
            return False
    return True


def clear_artifact_matches(execution_root: Path, pattern: str) -> None:
    for match in glob.glob(str(execution_root / pattern)):
        path = Path(match).resolve()
        try:
            path.relative_to(execution_root.resolve())
        except ValueError as error:
            raise ValueError(f"artifact path escapes execution root: {path}") from error
        if path.is_file():
            path.unlink()


def execute_phase(
    state: RunState,
    phase: str,
    include_package: bool = False,
) -> dict[str, Any]:
    if phase not in {"baseline", "target"}:
        raise ValueError(f"unsupported phase: {phase}")
    summary_path = state.root / "evidence" / f"{phase}-summary.json"
    summary_path.unlink(missing_ok=True)
    manifest = load_manifest(state.manifest_path)
    repository = Path(state.load_project()["source"]["workspace"]).resolve()
    root = execution_root(state)
    configured_source = contained_path(root, manifest["build"]["sourceDirectory"])
    if configured_source != repository:
        raise ValueError(
            f"manifest source directory resolves to {configured_source}, "
            f"but the verified workspace is {repository}"
        )
    verify_source_revision(manifest, repository)
    source_was_clean = not git_output(repository, "status", "--porcelain")

    _, active_path_entries, missing_path_entries = command_environment(manifest, {})
    probe_results = []
    for probe in manifest.get("toolchain", {}).get("probes", []):
        probe_results.append(
            execute_command(
                probe,
                manifest,
                phase,
                root,
                state.root,
                "prepare-target-build",
            )
        )
    environment_report = {
        "phase": phase,
        "configuredPathEntries": manifest.get("toolchain", {}).get(
            "pathEntries", []
        ),
        "activePathEntries": active_path_entries,
        "missingPathEntries": missing_path_entries,
        "probes": [
            {
                "id": result["commandId"],
                "outcome": result["outcome"],
                "exitCode": result["exitCode"],
            }
            for result in probe_results
        ],
    }
    write_json(
        state.root / "evidence" / "environment" / f"{phase}-toolchain.json",
        environment_report,
    )

    resources = prepare_resources(manifest, root)
    patches = apply_patches(manifest, repository, PORTPILOT_ROOT)
    verify_source_changes(
        manifest,
        repository,
        root,
        PORTPILOT_ROOT,
        state.root / "evidence" / "source" / "execution.json",
        source_was_clean,
    )
    build_results = []
    for command in manifest["build"]["commands"]:
        if phase not in command["phases"]:
            continue
        result = execute_command(
            command,
            manifest,
            phase,
            root,
            state.root,
            "prepare-target-build",
        )
        if result["outcome"] != "success":
            raise RuntimeError(
                f"{phase} build command {command['id']} did not succeed"
            )
        build_results.append(result)

    architecture = (
        verify_architecture(manifest, root, state.root)
        if phase == "target"
        else None
    )

    test_reports = []
    for suite in manifest["validation"]["testSuites"]:
        if phase not in suite["phases"]:
            continue
        result_path_template = suite.get("resultPath")
        if result_path_template:
            variables = template_values(manifest, phase)
            contained_path(
                root,
                expand(result_path_template, variables),
            ).unlink(missing_ok=True)
        result = execute_command(
            suite["command"],
            manifest,
            phase,
            root,
            state.root,
            "validate-target",
        )
        test_reports.append(
            evaluate_test_suite(
                suite,
                phase,
                manifest,
                root,
                state.root,
                result,
            )
        )

    scenario_reports = []
    for scenario in manifest["validation"]["scenarios"]:
        if phase not in scenario["phases"]:
            continue
        result = execute_command(
            scenario["command"],
            manifest,
            phase,
            root,
            state.root,
            "validate-target",
        )
        scenario_reports.append(
            evaluate_scenario(scenario, phase, root, state.root, result)
        )

    package_report = None
    if include_package:
        package = manifest["validation"].get("package")
        if not package:
            raise ValueError("manifest does not define package validation")
        clear_artifact_matches(root, package["artifactPattern"])
        package_result = execute_command(
            package["buildCommand"],
            manifest,
            "target",
            root,
            state.root,
            "validate-target",
        )
        if package_result["outcome"] != "success":
            raise RuntimeError("package build command did not succeed")
        matches = glob.glob(str(root / package["artifactPattern"]))
        if len(matches) != 1:
            raise RuntimeError(f"expected one wheel, found {len(matches)}")
        package_report = audit_wheel(Path(matches[0]), state.root, package)

    summary = {
        "phase": phase,
        "resources": resources,
        "environment": environment_report,
        "patches": patches,
        "buildCommands": len(build_results),
        "buildResults": [
            {"id": result["commandId"], "outcome": result["outcome"]}
            for result in build_results
        ],
        "testSuites": test_reports,
        "scenarios": scenario_reports,
        "architecture": architecture,
        "package": package_report,
    }
    verify_source_changes(
        manifest,
        repository,
        root,
        PORTPILOT_ROOT,
        state.root / "evidence" / "source" / "execution.json",
        source_was_clean=False,
    )
    write_json(summary_path, summary)
    return summary
