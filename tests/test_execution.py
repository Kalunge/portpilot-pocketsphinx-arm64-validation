from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

import yaml

from portpilot.execution.process import execute_command
from portpilot.execution.runner import (
    clear_artifact_matches,
    execute_phase,
    execution_is_complete,
)
from portpilot.execution.source import (
    apply_patches,
    prepare_resources,
    verify_source_changes,
)
from portpilot.execution.templates import contained_path, expand_command
from portpilot.execution.validation import (
    audit_wheel,
    evaluate_scenario,
    evaluate_test_suite,
    parse_failed_tests,
    read_pe_machine,
    verify_architecture,
)


def pe_bytes(machine: int) -> bytes:
    value = bytearray(128)
    value[0:2] = b"MZ"
    value[0x3C:0x40] = (0x40).to_bytes(4, "little")
    value[0x40:0x44] = b"PE\0\0"
    value[0x44:0x46] = machine.to_bytes(2, "little")
    return bytes(value)


class FakeState:
    def __init__(self, root: Path, manifest_path: Path, repository: Path) -> None:
        self.root = root
        self.manifest_path = manifest_path
        self.repository = repository

    def load_project(self) -> dict[str, object]:
        return {"source": {"workspace": str(self.repository)}}


class ExecutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.repository = self.root / "fixture"
        self.repository.mkdir()
        (self.repository / "tracked.txt").write_text("clean\n", encoding="utf-8")
        subprocess.run(["git", "init", "-q", str(self.repository)], check=True)
        subprocess.run(
            ["git", "-C", str(self.repository), "add", "tracked.txt"],
            check=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(self.repository),
                "-c",
                "user.name=PortPilot Tests",
                "-c",
                "user.email=portpilot@example.invalid",
                "commit",
                "-qm",
                "fixture",
            ],
            check=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(self.repository),
                "remote",
                "add",
                "origin",
                "https://example.invalid/fixture.git",
            ],
            check=True,
        )
        self.revision = subprocess.run(
            ["git", "-C", str(self.repository), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        self.run_directory = self.root / "run"
        (self.run_directory / "results").mkdir(parents=True)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def manifest(self) -> dict[str, object]:
        return {
            "source": {
                "repository": "https://example.invalid/fixture.git",
                "revision": self.revision,
                "checkoutDirectory": "fixture",
                "patches": [],
                "resources": [],
            },
            "target": {"configuration": "Release"},
            "build": {
                "sourceDirectory": "fixture",
                "buildDirectory": "fixture/build-${phase}",
                "variants": {
                    "baseline": {"platform": "x64"},
                    "target": {"platform": "ARM64"},
                },
                "definitions": {"BUILD_TESTING": True, "VALUE": 3},
                "commands": [],
            },
            "validation": {
                "architecture": {
                    "expectedMachine": "ARM64",
                    "files": ["fixture/app.exe"],
                },
                "testSuites": [],
                "scenarios": [],
            },
        }

    def test_templates_expand_to_individual_arguments(self) -> None:
        command = {
            "id": "configure",
            "executable": "cmake",
            "arguments": ["-B", "${buildDirectory}", "-A", "${platform}"],
            "appendDefinitions": True,
        }

        _, arguments, _ = expand_command(command, self.manifest(), "target")

        self.assertEqual(
            [
                "-B",
                "fixture/build-target",
                "-A",
                "ARM64",
                "-DBUILD_TESTING=ON",
                "-DVALUE=3",
            ],
            arguments,
        )

    def test_containment_and_executable_policy(self) -> None:
        with self.assertRaisesRegex(ValueError, "escapes"):
            contained_path(self.root, "../outside")
        command = {
            "id": "unsafe",
            "executable": "powershell",
            "arguments": [],
        }
        with self.assertRaisesRegex(ValueError, "allow-listed"):
            execute_command(
                command,
                self.manifest(),
                "baseline",
                self.root,
                self.run_directory,
                "prepare-target-build",
            )

    def test_process_result_and_capture_are_persisted(self) -> None:
        command = {
            "id": "hello",
            "executable": "python",
            "arguments": ["-c", "print('hello arm')"],
            "capture": "evidence/${phase}-hello.txt",
            "timeoutMinutes": 1,
        }

        result = execute_command(
            command,
            self.manifest(),
            "baseline",
            self.root,
            self.run_directory,
            "prepare-target-build",
        )

        self.assertEqual("success", result["outcome"])
        self.assertIn(
            "hello arm",
            (self.run_directory / result["stdoutPath"]).read_text(),
        )
        self.assertTrue(
            (self.run_directory / "results" / "baseline-hello.json").is_file()
        )

    def test_resource_download_requires_matching_hash(self) -> None:
        source = self.root / "source.bin"
        source.write_bytes(b"trusted resource")
        manifest = self.manifest()
        manifest["source"]["resources"] = [
            {
                "id": "fixture",
                "url": source.as_uri(),
                "path": "fixture/resource.bin",
                "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            }
        ]

        prepared = prepare_resources(manifest, self.root)

        self.assertEqual(b"trusted resource", Path(prepared[0]).read_bytes())

    def test_resource_hash_mismatch_is_rejected(self) -> None:
        source = self.root / "source.bin"
        source.write_bytes(b"unexpected")
        manifest = self.manifest()
        manifest["source"]["resources"] = [
            {
                "id": "fixture",
                "url": source.as_uri(),
                "path": "fixture/resource.bin",
                "sha256": hashlib.sha256(b"expected").hexdigest(),
            }
        ]

        with self.assertRaisesRegex(ValueError, "SHA-256"):
            prepare_resources(manifest, self.root)

        self.assertFalse((self.repository / "resource.bin").exists())

    def test_patch_application_is_idempotent(self) -> None:
        target = self.repository / "value.txt"
        target.write_text("before\n", encoding="utf-8")
        subprocess.run(["git", "init", "-q", str(self.repository)], check=True)
        patch = self.root / "change.patch"
        patch.write_text(
            "--- a/value.txt\n"
            "+++ b/value.txt\n"
            "@@ -1 +1 @@\n"
            "-before\n"
            "+after\n"
            "--- /dev/null\n"
            "+++ b/added.txt\n"
            "@@ -0,0 +1 @@\n"
            "+added\n",
            encoding="utf-8",
        )
        manifest = self.manifest()
        manifest["source"]["patches"] = [
            {
                "path": "change.patch",
                "strip": 1,
                "assertions": [{"path": "value.txt", "contains": "after"}],
            }
        ]

        first = apply_patches(manifest, self.repository, self.root)
        second = apply_patches(manifest, self.repository, self.root)

        self.assertEqual(first, second)
        self.assertEqual("after\n", target.read_text(encoding="utf-8"))
        self.assertEqual(
            "added\n",
            (self.repository / "added.txt").read_text(encoding="utf-8"),
        )
        verify_source_changes(
            manifest,
            self.repository,
            self.root,
            self.root,
            self.run_directory / "evidence" / "source" / "execution.json",
            source_was_clean=True,
        )

    def test_ctest_failure_parser_preserves_nested_identifiers(self) -> None:
        failure_log = self.root / "LastTestsFailed.log"
        failure_log.write_text(
            "59:_lcase1.test\n93:_fread_line.test\ninvalid:line\n",
            encoding="utf-8",
        )

        self.assertEqual(
            ["_fread_line.test", "_lcase1.test"],
            parse_failed_tests(failure_log),
        )

    def test_missing_optional_toolchain_path_does_not_hide_probe_failure(self) -> None:
        manifest = self.manifest()
        manifest["toolchain"] = {"pathEntries": [str(self.root / "missing")]}
        command = {
            "id": "probe",
            "executable": "python",
            "arguments": ["-c", "print('unused')"],
        }

        result = execute_command(
            command,
            manifest,
            "baseline",
            self.root,
            self.run_directory,
            "prepare-target-build",
        )

        self.assertEqual("success", result["outcome"])

    def test_pe_and_wheel_audits_detect_arm64(self) -> None:
        executable = self.repository / "app.exe"
        executable.write_bytes(pe_bytes(0xAA64))
        self.assertEqual(0xAA64, read_pe_machine(executable))

        wheel = self.root / "fixture-1.0-cp312-cp312-win_arm64.whl"
        with zipfile.ZipFile(wheel, "w") as archive:
            archive.writestr("fixture/native.pyd", pe_bytes(0xAA64))

        report = audit_wheel(
            wheel,
            self.run_directory,
            {
                "platformTag": "win_arm64",
                "nativeFiles": ["*.pyd"],
            },
        )

        self.assertTrue(report["nativeFiles"][0]["matches"])

    def test_wheel_audit_requires_declared_native_files(self) -> None:
        wheel = self.root / "fixture-1.0-cp312-cp312-win_arm64.whl"
        with zipfile.ZipFile(wheel, "w") as archive:
            archive.writestr("fixture/native.pyd", pe_bytes(0xAA64))

        with self.assertRaisesRegex(RuntimeError, "missing required native files"):
            audit_wheel(
                wheel,
                self.run_directory,
                {
                    "platformTag": "win_arm64",
                    "nativeFiles": ["*.dll"],
                },
            )

    def test_architecture_mismatch_is_rejected(self) -> None:
        (self.repository / "app.exe").write_bytes(pe_bytes(0x8664))

        with self.assertRaisesRegex(RuntimeError, "architecture mismatch"):
            verify_architecture(
                self.manifest(),
                self.root,
                self.run_directory,
            )

    def test_timeout_is_persisted(self) -> None:
        command = {
            "id": "timeout",
            "executable": "python",
            "arguments": ["-c", "import time; time.sleep(2)"],
            "timeoutMinutes": 0.001,
        }

        with self.assertRaisesRegex(RuntimeError, "timeout"):
            execute_command(
                command,
                self.manifest(),
                "baseline",
                self.root,
                self.run_directory,
                "prepare-target-build",
            )

        result = json.loads(
            (self.run_directory / "results" / "baseline-timeout.json").read_text()
        )
        self.assertEqual("timeout", result["outcome"])

    def test_expected_failure_requires_parseable_test_failures(self) -> None:
        suite = {
            "id": "tests",
            "failurePolicy": "no-new-failures",
            "knownFailures": [],
            "resultFormat": "ctest",
        }
        result = {"outcome": "expected-failure"}

        with self.assertRaisesRegex(RuntimeError, "parseable failure list"):
            evaluate_test_suite(
                suite,
                "baseline",
                self.manifest(),
                self.root,
                self.run_directory,
                result,
            )

    def test_scenario_output_mismatch_is_rejected(self) -> None:
        output = self.run_directory / "evidence" / "runtime.txt"
        output.parent.mkdir(parents=True)
        output.write_text("actual output\n", encoding="utf-8")
        scenario = {
            "id": "smoke",
            "expected": {
                "exitCode": 0,
                "outputContains": ["expected output"],
                "normalization": ["trim"],
            },
        }
        result = {
            "exitCode": 0,
            "stdoutPath": "evidence/runtime.txt",
        }

        with self.assertRaisesRegex(RuntimeError, "does not contain"):
            evaluate_scenario(
                scenario,
                "baseline",
                self.root,
                self.run_directory,
                result,
            )

    def test_full_baseline_adapter_executes_manifest(self) -> None:
        manifest = self.manifest()
        manifest["build"]["commands"] = [
            {
                "id": "build",
                "executable": "python",
                "arguments": ["-c", "print('build complete')"],
                "phases": ["baseline", "target"],
                "capture": "evidence/build/${phase}.txt",
            }
        ]
        manifest["validation"]["testSuites"] = [
            {
                "id": "tests",
                "phases": ["baseline"],
                "command": {
                    "id": "run-tests",
                    "executable": "python",
                    "arguments": ["-c", "print('tests pass')"],
                    "capture": "evidence/tests/${phase}.txt",
                },
                "resultFormat": "exit-code",
                "failurePolicy": "all-pass",
                "knownFailures": [],
            }
        ]
        manifest["validation"]["scenarios"] = [
            {
                "id": "smoke",
                "phases": ["baseline"],
                "command": {
                    "id": "run-smoke",
                    "executable": "python",
                    "arguments": ["-c", "print('hello arm')"],
                    "capture": "evidence/runtime/${phase}.txt",
                },
                "expected": {
                    "exitCode": 0,
                    "outputContains": ["hello arm"],
                    "normalization": ["trim", "lowercase"],
                },
            }
        ]
        manifest_path = self.root / "portpilot.yml"
        manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")
        state = FakeState(self.run_directory, manifest_path, self.repository)

        summary = execute_phase(state, "baseline")

        self.assertEqual(1, summary["buildCommands"])
        self.assertTrue(summary["testSuites"][0]["passed"])
        self.assertTrue(summary["scenarios"][0]["passed"])

    def test_adapter_rejects_a_different_logical_checkout(self) -> None:
        manifest = self.manifest()
        manifest["build"]["sourceDirectory"] = "another-checkout"
        manifest_path = self.root / "portpilot.yml"
        manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")
        state = FakeState(self.run_directory, manifest_path, self.repository)

        with self.assertRaisesRegex(ValueError, "verified workspace"):
            execute_phase(state, "baseline")

    def test_adapter_rejects_undeclared_source_changes(self) -> None:
        manifest = self.manifest()
        manifest_path = self.root / "portpilot.yml"
        manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")
        state = FakeState(self.run_directory, manifest_path, self.repository)
        (self.repository / "tracked.txt").write_text("modified\n", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "outside declared patches"):
            execute_phase(state, "baseline")

    def test_adapter_rechecks_source_after_commands(self) -> None:
        manifest = self.manifest()
        manifest["build"]["commands"] = [
            {
                "id": "mutate-source",
                "executable": "python",
                "arguments": [
                    "-c",
                    (
                        "from pathlib import Path; "
                        "Path('fixture/tracked.txt').write_text('changed\\n')"
                    ),
                ],
                "phases": ["baseline"],
            }
        ]
        manifest_path = self.root / "portpilot.yml"
        manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")
        state = FakeState(self.run_directory, manifest_path, self.repository)

        with self.assertRaisesRegex(ValueError, "outside declared patches"):
            execute_phase(state, "baseline")

        self.assertFalse(
            (self.run_directory / "evidence" / "baseline-summary.json").exists()
        )

    def test_stale_ctest_failure_log_cannot_satisfy_current_run(self) -> None:
        manifest = self.manifest()
        manifest_path = self.root / "portpilot.yml"
        manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")
        state = FakeState(self.run_directory, manifest_path, self.repository)
        execute_phase(state, "baseline")

        failure_log = (
            self.repository
            / "build-baseline"
            / "Testing"
            / "Temporary"
            / "LastTestsFailed.log"
        )
        failure_log.parent.mkdir(parents=True)
        failure_log.write_text("1:known-failure\n", encoding="utf-8")
        manifest["validation"]["testSuites"] = [
            {
                "id": "tests",
                "phases": ["baseline"],
                "command": {
                    "id": "run-tests",
                    "executable": "python",
                    "arguments": ["-c", "raise SystemExit(1)"],
                    "continueOnError": True,
                },
                "resultFormat": "ctest",
                "resultPath": (
                    "fixture/build-${phase}/Testing/Temporary/"
                    "LastTestsFailed.log"
                ),
                "failurePolicy": "no-new-failures",
                "knownFailures": ["known-failure"],
            }
        ]
        manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")

        with self.assertRaisesRegex(RuntimeError, "parseable failure list"):
            execute_phase(state, "baseline")

        self.assertFalse(failure_log.exists())

    def test_execution_completes_only_after_required_evidence(self) -> None:
        manifest = self.manifest()
        manifest_path = self.root / "portpilot.yml"
        manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")
        state = FakeState(self.run_directory, manifest_path, self.repository)
        evidence = self.run_directory / "evidence"
        evidence.mkdir(exist_ok=True)
        baseline = {
            "phase": "baseline",
            "buildCommands": 0,
            "buildResults": [],
            "environment": {"probes": []},
            "testSuites": [],
            "scenarios": [],
            "architecture": None,
            "package": None,
        }
        target = {
            **baseline,
            "phase": "target",
            "architecture": {
                "files": [{"path": "fixture/app.exe", "matches": True}]
            },
        }
        (evidence / "baseline-summary.json").write_text(
            json.dumps(baseline),
            encoding="utf-8",
        )

        self.assertFalse(execution_is_complete(state))

        (evidence / "target-summary.json").write_text(
            json.dumps(target),
            encoding="utf-8",
        )
        self.assertTrue(execution_is_complete(state))

        manifest["validation"]["package"] = {"kind": "python-wheel"}
        manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")
        self.assertFalse(execution_is_complete(state))

        target["package"] = {"wheel": "fixture.whl"}
        (evidence / "target-summary.json").write_text(
            json.dumps(target),
            encoding="utf-8",
        )
        self.assertTrue(execution_is_complete(state))

        target["architecture"]["files"] = []
        (evidence / "target-summary.json").write_text(
            json.dumps(target),
            encoding="utf-8",
        )
        self.assertFalse(execution_is_complete(state))

    def test_existing_package_artifacts_are_removed(self) -> None:
        wheelhouse = self.root / "wheelhouse"
        wheelhouse.mkdir()
        stale = wheelhouse / "fixture-1.0-cp312-cp312-win_arm64.whl"
        stale.write_bytes(b"stale")

        clear_artifact_matches(
            self.root,
            "wheelhouse/fixture-*-win_arm64.whl",
        )

        self.assertFalse(stale.exists())


if __name__ == "__main__":
    unittest.main()
