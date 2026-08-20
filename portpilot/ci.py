from __future__ import annotations

import fnmatch
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from portpilot.analysis.common import load_manifest, write_json
from portpilot.contracts import validate_contract
from portpilot.execution.process import execute_command
from portpilot.execution.runner import execution_root
from portpilot.execution.source import git_output, verify_source_revision
from portpilot.execution.templates import contained_path
from portpilot.execution.validation import audit_wheel
from portpilot.state import RunState


PACKAGE_PATTERN = re.compile(r"^[A-Za-z0-9_.+-]+$")


def manifest_metadata(manifest_path: Path) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    validate_contract("portpilot.schema.json", manifest)
    package = manifest["validation"].get("package")
    python = manifest["toolchain"].get("python", {})
    artifacts = manifest.get("artifacts", [])
    return {
        "projectId": manifest["project"]["id"],
        "checkoutDirectory": manifest["source"]["checkoutDirectory"],
        "repository": manifest["source"]["repository"],
        "revision": manifest["source"]["revision"],
        "baselineRunner": manifest["build"]["variants"]["baseline"]["runner"],
        "targetRunner": manifest["build"]["variants"]["target"]["runner"],
        "pythonVersion": python.get("version", "3.12"),
        "baselinePythonArchitecture": "x64",
        "targetPythonArchitecture": python.get(
            "architecture",
            manifest["target"]["architecture"],
        ),
        "hasPackage": package is not None,
        "retentionDays": max(
            (artifact["retentionDays"] for artifact in artifacts),
            default=30,
        ),
    }


def checkout_source(manifest_path: Path, workspace: Path) -> Path:
    manifest = load_manifest(manifest_path)
    validate_contract("portpilot.schema.json", manifest)
    workspace = workspace.resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    destination = contained_path(
        workspace,
        manifest["source"]["checkoutDirectory"],
    )
    if destination.exists():
        raise ValueError(f"source destination already exists: {destination}")
    commands = [
        [
            "git",
            "clone",
            "--no-checkout",
            manifest["source"]["repository"],
            str(destination),
        ],
        ["git", "-C", str(destination), "config", "core.autocrlf", "false"],
        [
            "git",
            "-C",
            str(destination),
            "checkout",
            "--detach",
            manifest["source"]["revision"],
        ],
    ]
    if manifest["source"].get("submodules"):
        commands.append(
            [
                "git",
                "-C",
                str(destination),
                "submodule",
                "update",
                "--init",
                "--recursive",
            ]
        )
    for command in commands:
        completed = subprocess.run(
            command,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if completed.returncode != 0:
            raise RuntimeError(f"{' '.join(command[:2])} failed")
    verify_source_revision(manifest, destination)
    if git_output(destination, "status", "--porcelain"):
        raise RuntimeError("new source checkout is not clean")
    return destination


def bootstrap_toolchain(manifest_path: Path) -> list[dict[str, Any]]:
    manifest = load_manifest(manifest_path)
    validate_contract("portpilot.schema.json", manifest)
    results = []
    for dependency in manifest["toolchain"]["dependencies"]:
        manager = dependency["manager"]
        packages = dependency["packages"]
        invalid = [value for value in packages if not PACKAGE_PATTERN.fullmatch(value)]
        if invalid:
            raise ValueError(f"invalid {manager} package names: {', '.join(invalid)}")
        if manager == "chocolatey":
            command = ["choco", "install", *packages, "-y", "--no-progress"]
        elif manager == "pip":
            command = ["python", "-m", "pip", "install", *packages]
        elif manager == "winget":
            if len(packages) != 1:
                raise ValueError("winget dependencies must contain one package")
            command = [
                "winget",
                "install",
                "--id",
                packages[0],
                "--exact",
                "--silent",
                "--accept-package-agreements",
                "--accept-source-agreements",
            ]
        else:
            raise ValueError(f"unsupported package manager: {manager}")
        completed = subprocess.run(command, check=False)
        if completed.returncode != 0:
            raise RuntimeError(f"{manager} dependency installation failed")
        results.append({"manager": manager, "packages": packages})
    return results


def assert_trusted_manifest(state: RunState, trusted_manifest_path: Path) -> dict[str, Any]:
    stored_manifest = load_manifest(state.manifest_path)
    trusted_manifest = load_manifest(trusted_manifest_path)
    validate_contract("portpilot.schema.json", trusted_manifest)
    if stored_manifest != trusted_manifest:
        raise ValueError("downloaded run manifest differs from the trusted manifest")
    project = state.load_project()
    expected = {
        "projectId": trusted_manifest["project"]["id"],
        "repository": trusted_manifest["source"]["repository"],
        "revision": trusted_manifest["source"]["revision"],
        "checkoutDirectory": trusted_manifest["source"]["checkoutDirectory"],
        "architecture": trusted_manifest["target"]["architecture"],
    }
    actual = {
        "projectId": project["projectId"],
        "repository": project["source"]["repository"],
        "revision": project["source"]["revision"],
        "checkoutDirectory": project["source"]["checkoutDirectory"],
        "architecture": project["target"]["architecture"],
    }
    if actual != expected:
        raise ValueError("downloaded run identity differs from the trusted manifest")
    return trusted_manifest


def rebind_workspace(
    state: RunState,
    repository: Path,
    trusted_manifest_path: Path,
) -> dict[str, Any]:
    manifest = assert_trusted_manifest(state, trusted_manifest_path)
    repository = repository.resolve()
    if repository.name != manifest["source"]["checkoutDirectory"]:
        raise ValueError(
            f"workspace directory is {repository.name}, expected "
            f"{manifest['source']['checkoutDirectory']}"
        )
    verify_source_revision(manifest, repository)
    if git_output(repository, "status", "--porcelain"):
        raise ValueError("replacement source checkout is not clean")
    project = state.load_project()
    project["source"]["workspace"] = str(repository)
    state.save_project(project)
    return project["source"]


def consume_package(
    state: RunState,
    artifacts_directory: Path,
    trusted_manifest_path: Path,
) -> dict[str, Any]:
    manifest = assert_trusted_manifest(state, trusted_manifest_path)
    package = manifest["validation"].get("package")
    if not package:
        raise ValueError("manifest does not define package validation")
    repository = Path(state.load_project()["source"]["workspace"]).resolve()
    verify_source_revision(manifest, repository)
    if git_output(repository, "status", "--porcelain"):
        raise ValueError("clean-install source checkout is not clean")

    filename_pattern = Path(package["artifactPattern"]).name
    wheels = [
        path
        for path in artifacts_directory.resolve().rglob("*")
        if path.is_file() and fnmatch.fnmatch(path.name, filename_pattern)
    ]
    if len(wheels) != 1:
        raise RuntimeError(f"expected one wheel, found {len(wheels)}")
    wheel = wheels[0]
    audit_wheel(wheel, state.root, package)

    results = []
    root = execution_root(state)
    for command in package["cleanInstall"]["commands"]:
        result = execute_command(
            command,
            manifest,
            "target",
            root,
            state.root,
            "validate-target",
            {"wheel": str(wheel)},
        )
        if result["outcome"] != "success":
            raise RuntimeError(
                f"clean-install command {command['id']} did not succeed"
            )
        results.append(
            {"id": result["commandId"], "outcome": result["outcome"]}
        )
    report = {"wheel": wheel.name, "commands": results, "passed": True}
    write_json(state.root / "evidence" / "package" / "clean-install.json", report)
    return report


def collect_artifacts(
    state: RunState,
    output_directory: Path,
) -> dict[str, Any]:
    manifest = load_manifest(state.manifest_path)
    root = execution_root(state)
    output_directory = output_directory.resolve()
    if output_directory.exists():
        raise ValueError(f"artifact output already exists: {output_directory}")
    output_directory.mkdir(parents=True)
    copied = []
    for artifact in manifest.get("artifacts", []):
        for pattern in artifact["paths"]:
            for match in root.glob(pattern.replace("\\", "/")):
                source = match.resolve()
                try:
                    relative = source.relative_to(root)
                except ValueError as error:
                    raise ValueError(
                        f"artifact path escapes execution root: {source}"
                    ) from error
                destination = output_directory / "application" / relative
                if source.is_dir():
                    shutil.copytree(source, destination, dirs_exist_ok=True)
                elif source.is_file():
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)
                copied.append(str(relative).replace("\\", "/"))
    shutil.copytree(state.root, output_directory / "run")
    report = {"applicationPaths": sorted(set(copied)), "runDirectory": "run"}
    write_json(output_directory / "artifact-index.json", report)
    return report
