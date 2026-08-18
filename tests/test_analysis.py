from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from portpilot.analysis.architecture_selector import select_architecture
from portpilot.analysis.compatibility_scanner import scan_repository
from portpilot.analysis.dependency_inventory import (
    inventory_dependencies,
    native_dependency_summary,
)
from portpilot.analysis.repository_profiler import profile_repository


ROOT = Path(__file__).resolve().parents[1]


class AnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.repository = Path(self.temporary_directory.name)
        (self.repository / "src").mkdir()
        (self.repository / "third_party" / "portable").mkdir(parents=True)
        (self.repository / ".github" / "workflows").mkdir(parents=True)
        (self.repository / "CMakeLists.txt").write_text(
            """
            cmake_minimum_required(VERSION 3.25)
            project(fixture CXX)
            find_package(OpenSSL REQUIRED)
            add_subdirectory(third_party/portable)
            set(LEGACY_LIBRARY lib/x64/legacy.lib)
            add_executable(fixture src/main.cpp)
            """,
            encoding="utf-8",
        )
        (self.repository / "src" / "main.cpp").write_text(
            """
            #include <immintrin.h>
            int main() {
                __m128 value = _mm_setzero_ps();
                return _M_X64 ? (int)_mm_cvtss_f32(value) : 0;
            }
            """,
            encoding="utf-8",
        )
        (self.repository / "third_party" / "portable" / "CMakeLists.txt").write_text(
            "project(portable C)\n",
            encoding="utf-8",
        )
        (self.repository / ".github" / "workflows" / "build.yml").write_text(
            """
            jobs:
              windows:
                runs-on: windows-latest
                strategy:
                  matrix:
                    arch: [x64]
            """,
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def validate(self, schema_name: str, value: object) -> None:
        schema = json.loads((ROOT / "schemas" / schema_name).read_text())
        Draft202012Validator(
            schema,
            format_checker=FormatChecker(),
        ).validate(value)

    def test_analysis_outputs_are_structured_and_select_native_arm64(self) -> None:
        dependencies = inventory_dependencies(self.repository, "fixture")
        inventory = profile_repository(
            self.repository,
            "fixture",
            native_dependency_summary(dependencies),
        )
        findings = scan_repository(self.repository, "fixture")
        decision = select_architecture(
            "fixture",
            inventory,
            dependencies,
            findings,
        )

        self.assertIn("cmake", inventory["buildSystems"])
        self.assertIn(
            "OpenSSL",
            {item["name"] for item in dependencies["dependencies"]},
        )
        self.assertIn(
            "x86-intrinsic",
            {item["category"] for item in findings},
        )
        self.assertIn(
            "packaging",
            {item["category"] for item in findings},
        )
        self.assertIn(
            "build-system",
            {item["category"] for item in findings},
        )
        self.assertEqual("arm64", decision["selectedArchitecture"])

        self.validate("dependency-inventory.schema.json", dependencies)
        self.validate("inventory.schema.json", inventory)
        for finding in findings:
            self.validate("finding.schema.json", finding)
        self.validate("architecture-decision.schema.json", decision)

    def test_x64_only_dependency_selects_arm64ec(self) -> None:
        dependencies = {
            "projectId": "fixture",
            "generatedAt": "2026-08-18T00:00:00Z",
            "dependencies": [
                {
                    "name": "legacy-codec",
                    "kind": "cmake-package",
                    "source": "CMakeLists.txt",
                    "evidence": "find_package(legacy-codec)",
                    "role": "runtime",
                    "inProcess": True,
                    "architectures": ["x64"],
                }
            ],
        }
        inventory = profile_repository(
            self.repository,
            "fixture",
            native_dependency_summary(dependencies),
        )
        decision = select_architecture("fixture", inventory, dependencies, [])

        self.assertEqual("arm64ec", decision["selectedArchitecture"])
        self.assertTrue(
            any("legacy-codec" in blocker for blocker in decision["blockers"])
        )

    def test_unresolved_blocker_stops_architecture_selection(self) -> None:
        dependencies = inventory_dependencies(self.repository, "fixture")
        inventory = profile_repository(
            self.repository,
            "fixture",
            native_dependency_summary(dependencies),
        )
        findings = [
            {
                "id": "PP-FIXTURE-001",
                "category": "assembly",
                "severity": "blocker",
            }
        ]

        decision = select_architecture(
            "fixture",
            inventory,
            dependencies,
            findings,
        )

        self.assertEqual("blocked", decision["selectedArchitecture"])

    def test_x64_only_build_tool_does_not_select_arm64ec(self) -> None:
        dependencies = {
            "projectId": "fixture",
            "generatedAt": "2026-08-18T00:00:00Z",
            "dependencies": [
                {
                    "name": "code-generator",
                    "kind": "cmake-package",
                    "source": "CMakeLists.txt",
                    "evidence": "find_package(code-generator)",
                    "role": "build",
                    "inProcess": False,
                    "architectures": ["x64"],
                }
            ],
        }
        inventory = profile_repository(
            self.repository,
            "fixture",
            native_dependency_summary(dependencies),
        )

        decision = select_architecture("fixture", inventory, dependencies, [])

        self.assertEqual("arm64", decision["selectedArchitecture"])


if __name__ == "__main__":
    unittest.main()
