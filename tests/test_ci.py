from __future__ import annotations

import copy
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

from portpilot.ci import collect_artifacts, manifest_metadata, rebind_workspace
from portpilot.state import RunState


ROOT = Path(__file__).resolve().parents[1]


class CiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.repository = self.root / "fixture"
        self.repository.mkdir()
        (self.repository / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.25)\nproject(fixture C)\n",
            encoding="utf-8",
        )
        self.git("init")
        self.git("config", "user.email", "portpilot@example.invalid")
        self.git("config", "user.name", "PortPilot Tests")
        self.git("remote", "add", "origin", "https://example.com/fixture.git")
        self.git("add", ".")
        self.git("commit", "-m", "fixture")
        self.revision = self.git("rev-parse", "HEAD")

        manifest = copy.deepcopy(
            yaml.safe_load(
                (
                    ROOT / "manifests" / "whisper-cpp" / "portpilot.yml"
                ).read_text(encoding="utf-8")
            )
        )
        manifest["project"].update(
            {
                "id": "fixture",
                "name": "Fixture",
                "version": "1.0",
                "homepage": "https://example.com/fixture",
            }
        )
        manifest["source"].update(
            {
                "repository": "https://example.com/fixture.git",
                "revision": self.revision,
                "checkoutDirectory": "fixture",
                "resources": [],
            }
        )
        manifest["artifacts"] = [
            {
                "id": "evidence",
                "paths": ["fixture/build-target/*.exe"],
                "retentionDays": 7,
            }
        ]
        self.manifest_path = self.root / "portpilot.yml"
        self.manifest_path.write_text(
            yaml.safe_dump(manifest, sort_keys=False),
            encoding="utf-8",
        )
        self.state = RunState.create_or_load(
            self.manifest_path,
            self.repository,
            self.root / "runs",
            "fixture-ci",
        )

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

    def test_reference_manifest_metadata_drives_ci(self) -> None:
        pocketsphinx = manifest_metadata(
            ROOT / "manifests" / "pocketsphinx" / "portpilot.yml"
        )
        whisper = manifest_metadata(
            ROOT / "manifests" / "whisper-cpp" / "portpilot.yml"
        )

        self.assertEqual("windows-2025", pocketsphinx["baselineRunner"])
        self.assertEqual("windows-11-arm", pocketsphinx["targetRunner"])
        self.assertTrue(pocketsphinx["hasPackage"])
        self.assertFalse(whisper["hasPackage"])

    def test_rebind_requires_clean_pinned_checkout(self) -> None:
        replacement_root = self.root / "replacement"
        replacement = replacement_root / "fixture"
        replacement_root.mkdir()
        subprocess.run(
            ["git", "clone", "-q", str(self.repository), str(replacement)],
            check=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(replacement),
                "remote",
                "set-url",
                "origin",
                "https://example.com/fixture.git",
            ],
            check=True,
        )

        source = rebind_workspace(
            self.state,
            replacement,
            self.manifest_path,
        )

        self.assertEqual(str(replacement.resolve()), source["workspace"])

        (replacement / "CMakeLists.txt").write_text("changed\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "not clean"):
            rebind_workspace(self.state, replacement, self.manifest_path)

    def test_rebind_rejects_tampered_downloaded_manifest(self) -> None:
        replacement_root = self.root / "replacement"
        replacement = replacement_root / "fixture"
        replacement_root.mkdir()
        subprocess.run(
            ["git", "clone", "-q", str(self.repository), str(replacement)],
            check=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(replacement),
                "remote",
                "set-url",
                "origin",
                "https://example.com/fixture.git",
            ],
            check=True,
        )
        downloaded = yaml.safe_load(
            self.state.manifest_path.read_text(encoding="utf-8")
        )
        downloaded["validation"]["scenarios"][0]["command"]["arguments"] = [
            "-c",
            "print('tampered')",
        ]
        self.state.manifest_path.write_text(
            yaml.safe_dump(downloaded, sort_keys=False),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "trusted manifest"):
            rebind_workspace(self.state, replacement, self.manifest_path)

    def test_artifact_collection_uses_fixed_layout(self) -> None:
        executable = self.repository / "build-target" / "fixture.exe"
        executable.parent.mkdir()
        executable.write_bytes(b"fixture")
        (self.state.root / "evidence" / "summary.json").write_text(
            "{}\n",
            encoding="utf-8",
        )

        output = self.root / "bundle"
        report = collect_artifacts(self.state, output)

        self.assertEqual(["fixture/build-target/fixture.exe"], report["applicationPaths"])
        self.assertTrue(
            (
                output
                / "application"
                / "fixture"
                / "build-target"
                / "fixture.exe"
            ).is_file()
        )
        self.assertTrue((output / "run" / "project.json").is_file())
        self.assertTrue((output / "artifact-index.json").is_file())


if __name__ == "__main__":
    unittest.main()
