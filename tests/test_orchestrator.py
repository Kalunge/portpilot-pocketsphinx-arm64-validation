from __future__ import annotations

import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

from portpilot.analysis.common import read_json, write_json
from portpilot.orchestrator import (
    run_analysis_stage,
    run_pipeline,
    update_task_status,
)
from portpilot.planner import assert_acyclic
from portpilot.reporting import create_report
from portpilot.state import RunState


ROOT = Path(__file__).resolve().parents[1]


class OrchestratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.repository = self.root / "fixture"
        self.repository.mkdir()
        (self.repository / "src").mkdir()
        (self.repository / "CMakeLists.txt").write_text(
            """
            cmake_minimum_required(VERSION 3.25)
            project(fixture C)
            add_executable(fixture src/main.c)
            """,
            encoding="utf-8",
        )
        (self.repository / "src" / "main.c").write_text(
            """
            #include <immintrin.h>
            int main(void) {
                __m128 value = _mm_setzero_ps();
                return (int)_mm_cvtss_f32(value);
            }
            """,
            encoding="utf-8",
        )
        self.git("init")
        self.git("config", "user.email", "portpilot@example.invalid")
        self.git("config", "user.name", "PortPilot Tests")
        self.git("remote", "add", "origin", "https://example.com/fixture.git")
        self.git("add", ".")
        self.git("commit", "-m", "fixture")
        self.revision = self.git("rev-parse", "HEAD")

        source_manifest = yaml.safe_load(
            (ROOT / "manifests" / "pocketsphinx" / "portpilot.yml").read_text(
                encoding="utf-8"
            )
        )
        manifest = copy.deepcopy(source_manifest)
        manifest["project"] = {
            "id": "fixture",
            "name": "Fixture",
            "version": "1.0",
            "license": "MIT",
            "homepage": "https://example.com/fixture",
        }
        manifest["source"].update(
            {
                "repository": "https://example.com/fixture.git",
                "revision": self.revision,
                "checkoutDirectory": "fixture",
                "patches": [],
                "resources": [],
            }
        )
        self.manifest_path = self.root / "portpilot.yml"
        self.manifest_path.write_text(
            yaml.safe_dump(manifest, sort_keys=False),
            encoding="utf-8",
        )
        self.runs_directory = self.root / "runs"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def git(self, *arguments: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(self.repository), *arguments],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        return result.stdout.strip()

    def create_state(self, run_id: str = "fixture-run") -> RunState:
        return RunState.create_or_load(
            self.manifest_path,
            self.repository,
            self.runs_directory,
            run_id,
        )

    def test_pipeline_creates_resumable_plan_and_report(self) -> None:
        state = self.create_state()

        first_status = run_pipeline(state)
        project = state.load_project()
        graph = read_json(state.root / "task-graph.json")
        report = read_json(state.root / "report.json")

        self.assertFalse(first_status["resumed"])
        self.assertEqual("planned", project["status"])
        self.assertEqual("done", project["stages"]["analysis"])
        self.assertEqual("done", project["stages"]["planning"])
        self.assertEqual("pending", project["stages"]["execution"])
        self.assertEqual("done", project["stages"]["reporting"])
        self.assertEqual("not-ready", report["verdict"])
        self.assertGreater(len(graph["tasks"]), 1)
        self.assertEqual(["prepare-target-build"], first_status["readyTasks"])

        second_status = run_pipeline(state)

        self.assertTrue(second_status["resumed"])
        self.assertEqual(first_status["tasks"], second_status["tasks"])

    def test_completed_tasks_cannot_bypass_execution_evidence(self) -> None:
        state = self.create_state()
        run_pipeline(state)
        for path in (state.root / "tasks").glob("*.json"):
            task = read_json(path)
            task["status"] = "done"
            write_json(path, task)

        report = create_report(state.root)

        self.assertEqual("not-ready", report["verdict"])
        tests_gate = next(
            gate for gate in report["gates"] if gate["id"] == "tests"
        )
        self.assertEqual("not-applicable", tests_gate["status"])
        self.assertIn("Execution evidence is incomplete.", report["remainingRisks"])

    def test_dirty_source_fails_analysis_without_success_state(self) -> None:
        state = self.create_state("dirty-run")
        (self.repository / "src" / "main.c").write_text(
            "int changed(void) { return 1; }\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "not clean"):
            run_analysis_stage(state)

        project = state.load_project()
        self.assertEqual("failed", project["status"])
        self.assertEqual("failed", project["stages"]["analysis"])

    def test_task_transitions_unlock_dependents(self) -> None:
        state = self.create_state()
        run_pipeline(state)

        update_task_status(state, "prepare-target-build", "in-progress")
        update_task_status(state, "prepare-target-build", "review")
        self.assertEqual("running", state.load_project()["status"])
        self.assertFalse((state.root / "report.json").exists())
        update_task_status(state, "prepare-target-build", "done")

        remediation = read_json(
            state.root / "tasks" / "resolve-x86-simd-remediation.json"
        )
        self.assertEqual("ready", remediation["status"])
        self.assertEqual(1, read_json(
            state.root / "tasks" / "prepare-target-build.json"
        )["attempts"])

    def test_task_id_cannot_escape_run_directory(self) -> None:
        state = self.create_state()
        run_pipeline(state)

        with self.assertRaisesRegex(ValueError, "invalid task ID"):
            update_task_status(
                state,
                "../../another-run/tasks/prepare-target-build",
                "in-progress",
            )

    def test_run_lock_rejects_concurrent_writer(self) -> None:
        state = self.create_state()

        with state.lock():
            with self.assertRaisesRegex(RuntimeError, "locked"):
                with state.lock():
                    pass

    def test_cycle_detection_rejects_invalid_graph(self) -> None:
        tasks = [
            {"id": "first", "dependsOn": ["second"]},
            {"id": "second", "dependsOn": ["first"]},
        ]

        with self.assertRaisesRegex(ValueError, "cycle"):
            assert_acyclic(tasks)


if __name__ == "__main__":
    unittest.main()
