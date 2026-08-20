from __future__ import annotations

import json
import os
import re
import shutil
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any

from portpilot.analysis.common import load_manifest, read_json, utc_now, write_json
from portpilot.contracts import validate_contract


RUN_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
STAGES = ("analysis", "planning", "execution", "reporting")


class RunLock(AbstractContextManager["RunLock"]):
    def __init__(self, run_directory: Path) -> None:
        self.path = run_directory / ".portpilot.lock"
        self.acquired = False

    def __enter__(self) -> "RunLock":
        try:
            with self.path.open("x", encoding="utf-8") as stream:
                json.dump({"pid": os.getpid(), "createdAt": utc_now()}, stream)
                stream.write("\n")
        except FileExistsError as error:
            raise RuntimeError(
                f"Run is locked by {self.path}. Confirm no PortPilot process is "
                "active before removing a stale lock."
            ) from error
        self.acquired = True
        return self

    def __exit__(self, *args: object) -> None:
        if self.acquired:
            self.path.unlink(missing_ok=True)
            self.acquired = False


class RunState:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.project_path = self.root / "project.json"
        self.manifest_path = self.root / "portpilot.yml"

    @classmethod
    def create_or_load(
        cls,
        manifest_path: Path,
        repository: Path,
        runs_directory: Path,
        run_id: str,
    ) -> "RunState":
        if not RUN_ID_PATTERN.fullmatch(run_id):
            raise ValueError(
                "run ID must contain only lowercase letters, digits, and hyphens"
            )
        manifest = load_manifest(manifest_path)
        validate_contract("portpilot.schema.json", manifest)
        repository = repository.resolve()
        runs_directory = runs_directory.resolve()
        root = runs_directory / run_id
        state = cls(root)
        if root.exists():
            state.assert_matches(manifest, repository)
            return state

        runs_directory.mkdir(parents=True, exist_ok=True)
        temporary_root = runs_directory / f".{run_id}.creating-{os.getpid()}"
        temporary_root.mkdir()
        try:
            for directory in ("evidence", "results", "tasks"):
                (temporary_root / directory).mkdir()
            shutil.copyfile(manifest_path, temporary_root / "portpilot.yml")
            timestamp = utc_now()
            project = {
                "runId": run_id,
                "manifest": "portpilot.yml",
                "projectId": manifest["project"]["id"],
                "source": {
                    "repository": manifest["source"]["repository"],
                    "revision": manifest["source"]["revision"],
                    "checkoutDirectory": manifest["source"]["checkoutDirectory"],
                    "workspace": str(repository),
                },
                "target": {
                    "operatingSystem": manifest["target"]["operatingSystem"],
                    "architecture": manifest["target"]["architecture"],
                },
                "status": "created",
                "stages": {stage: "pending" for stage in STAGES},
                "createdAt": timestamp,
                "updatedAt": timestamp,
            }
            validate_contract("project.schema.json", project)
            write_json(temporary_root / "project.json", project)
            temporary_root.replace(root)
        except BaseException:
            if temporary_root.exists():
                shutil.rmtree(temporary_root)
            raise
        return state

    @classmethod
    def load(cls, root: Path) -> "RunState":
        state = cls(root)
        if not state.project_path.is_file() or not state.manifest_path.is_file():
            raise ValueError(f"{root} is not a PortPilot run directory")
        state.load_project()
        return state

    def assert_matches(self, manifest: dict[str, Any], repository: Path) -> None:
        project = self.load_project()
        stored_manifest = load_manifest(self.manifest_path)
        if stored_manifest != manifest:
            raise ValueError(
                f"{self.root} was created from a different manifest; "
                "use a new run ID"
            )
        if Path(project["source"]["workspace"]).resolve() != repository:
            raise ValueError(
                f"{self.root} belongs to workspace "
                f"{project['source']['workspace']}, not {repository}"
            )

    def load_project(self) -> dict[str, Any]:
        project = read_json(self.project_path)
        validate_contract("project.schema.json", project)
        return project

    def save_project(self, project: dict[str, Any]) -> None:
        project["updatedAt"] = utc_now()
        validate_contract("project.schema.json", project)
        write_json(self.project_path, project)

    def transition(
        self,
        stage: str,
        stage_status: str,
        project_status: str,
    ) -> dict[str, Any]:
        if stage not in STAGES:
            raise ValueError(f"unknown stage: {stage}")
        project = self.load_project()
        project["stages"][stage] = stage_status
        project["status"] = project_status
        self.save_project(project)
        return project

    def lock(self) -> RunLock:
        return RunLock(self.root)

