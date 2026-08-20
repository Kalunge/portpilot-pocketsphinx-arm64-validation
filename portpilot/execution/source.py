from __future__ import annotations

import hashlib
import json
import subprocess
import urllib.request
from pathlib import Path
from typing import Any

from portpilot.execution.templates import contained_path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_output(repository: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"git {' '.join(arguments)} failed: {message}")
    return completed.stdout.strip()


def normalized_repository_url(value: str) -> str:
    return value.removesuffix(".git").rstrip("/").lower()


def verify_source_revision(manifest: dict[str, Any], repository: Path) -> None:
    if not (repository / ".git").exists():
        raise ValueError(f"{repository} is not a Git checkout")
    revision = git_output(repository, "rev-parse", "HEAD")
    expected_revision = manifest["source"]["revision"]
    if revision != expected_revision:
        raise ValueError(
            f"source revision is {revision}, expected {expected_revision}"
        )
    origin = git_output(repository, "remote", "get-url", "origin")
    expected_origin = manifest["source"]["repository"]
    if normalized_repository_url(origin) != normalized_repository_url(
        expected_origin
    ):
        raise ValueError(f"source origin is {origin}, expected {expected_origin}")


def patch_paths(
    manifest: dict[str, Any],
    repository: Path,
    portpilot_root: Path,
) -> set[str]:
    paths = set()
    for patch in manifest["source"].get("patches", []):
        patch_path = contained_path(portpilot_root, patch["path"])
        output = git_output(
            repository,
            "apply",
            "--numstat",
            f"-p{patch.get('strip', 1)}",
            str(patch_path),
        )
        for line in output.splitlines():
            columns = line.split("\t", 2)
            if len(columns) == 3:
                paths.add(columns[2].replace("\\", "/"))
    return paths


def verify_source_changes(
    manifest: dict[str, Any],
    repository: Path,
    execution_root: Path,
    portpilot_root: Path,
    evidence_path: Path,
    source_was_clean: bool,
) -> None:
    expected_tracked = patch_paths(manifest, repository, portpilot_root)
    actual_tracked = {
        value.replace("\\", "/")
        for value in git_output(repository, "diff", "--name-only", "HEAD").splitlines()
        if value
    }
    unexpected_tracked = actual_tracked - expected_tracked

    allowed_untracked_roots = []
    source_root = repository.resolve()
    for phase in ("baseline", "target"):
        build_path = contained_path(
            execution_root,
            manifest["build"]["buildDirectory"].replace("${phase}", phase),
        )
        try:
            allowed_untracked_roots.append(build_path.relative_to(source_root))
        except ValueError:
            pass
    allowed_untracked_files = []
    for resource in manifest["source"].get("resources", []):
        resource_path = contained_path(execution_root, resource["path"])
        try:
            allowed_untracked_files.append(resource_path.relative_to(source_root))
        except ValueError:
            pass

    unexpected_untracked = []
    patch_file_paths = {Path(value) for value in expected_tracked}
    for value in git_output(
        repository, "ls-files", "--others", "--exclude-standard"
    ).splitlines():
        relative = Path(value)
        if relative in patch_file_paths:
            continue
        if relative in allowed_untracked_files:
            continue
        if any(
            relative == root or root in relative.parents
            for root in allowed_untracked_roots
        ):
            continue
        unexpected_untracked.append(value)

    if unexpected_tracked or unexpected_untracked:
        details = sorted(unexpected_tracked) + sorted(unexpected_untracked)
        raise ValueError(
            "source checkout contains changes outside declared patches, "
            f"resources, or build directories: {', '.join(details)}"
        )

    tracked_files = {}
    for value in sorted(expected_tracked):
        path = contained_path(repository, value)
        tracked_files[value] = sha256(path) if path.is_file() else None
    source_record = {
        "revision": git_output(repository, "rev-parse", "HEAD"),
        "origin": git_output(repository, "remote", "get-url", "origin"),
        "patchedFiles": tracked_files,
    }
    if evidence_path.is_file():
        previous = json.loads(evidence_path.read_text(encoding="utf-8"))
        if previous != source_record:
            raise ValueError("source patch state differs from recorded execution evidence")
    else:
        if not source_was_clean:
            raise ValueError(
                "source checkout was already modified before patch evidence was recorded"
            )
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = evidence_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(source_record, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(evidence_path)


def prepare_resources(
    manifest: dict[str, Any],
    execution_root: Path,
) -> list[str]:
    prepared = []
    for resource in manifest["source"].get("resources", []):
        destination = contained_path(execution_root, resource["path"])
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.is_file() and sha256(destination) == resource["sha256"]:
            prepared.append(str(destination))
            continue
        temporary = destination.with_suffix(destination.suffix + ".download")
        temporary.unlink(missing_ok=True)
        try:
            request = urllib.request.Request(
                resource["url"],
                headers={"User-Agent": "PortPilot/0.1"},
            )
            with urllib.request.urlopen(request, timeout=120) as response:
                with temporary.open("wb") as stream:
                    while chunk := response.read(1024 * 1024):
                        stream.write(chunk)
            actual = sha256(temporary)
            if actual != resource["sha256"]:
                raise ValueError(
                    f"resource {resource['id']} SHA-256 is {actual}, "
                    f"expected {resource['sha256']}"
                )
            temporary.replace(destination)
            prepared.append(str(destination))
        finally:
            temporary.unlink(missing_ok=True)
    return prepared


def apply_patches(
    manifest: dict[str, Any],
    repository: Path,
    portpilot_root: Path,
) -> list[str]:
    applied = []
    for patch in manifest["source"].get("patches", []):
        patch_path = contained_path(portpilot_root, patch["path"])
        if not patch_path.is_file():
            raise ValueError(f"patch does not exist: {patch['path']}")
        strip = patch.get("strip", 1)
        apply_arguments = [f"-p{strip}", str(patch_path)]
        reverse = subprocess.run(
            [
                "git",
                "-C",
                str(repository),
                "apply",
                "--reverse",
                "--check",
                *apply_arguments,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if reverse.returncode != 0:
            completed = subprocess.run(
                ["git", "-C", str(repository), "apply", *apply_arguments],
                capture_output=True,
                text=True,
                check=False,
            )
            if completed.returncode != 0:
                raise RuntimeError(
                    f"failed to apply {patch['path']}: {completed.stderr.strip()}"
                )
        for assertion in patch.get("assertions", []):
            target = contained_path(repository, assertion["path"])
            if assertion["contains"] not in target.read_text(
                encoding="utf-8",
                errors="replace",
            ):
                raise ValueError(
                    f"patch assertion failed: {assertion['path']} does not "
                    f"contain {assertion['contains']}"
                )
        applied.append(str(patch_path))
    return applied
