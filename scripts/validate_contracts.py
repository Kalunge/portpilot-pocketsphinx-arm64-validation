#!/usr/bin/env python3

import copy
import json
import re
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIRECTORY = ROOT / "schemas"
MANIFEST_PATTERN = "manifests/*/portpilot.yml"
ALLOWED_TEMPLATES = {
    "phase",
    "sourceDirectory",
    "buildDirectory",
    "platform",
    "configuration",
    "wheel",
}
TEMPLATE_PATTERN = re.compile(r"\$\{([^}]+)\}")


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as stream:
        value = yaml.safe_load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a YAML object")
    return value


def format_error(path: Path, error: ValidationError) -> str:
    location = ".".join(str(part) for part in error.absolute_path) or "<root>"
    return f"{path}: {location}: {error.message}"


def manifest_ids(manifest: dict) -> list[str]:
    validation = manifest["validation"]
    identifiers = [
        resource["id"] for resource in manifest["source"].get("resources", [])
    ]
    identifiers.extend(command["id"] for command in manifest["toolchain"]["probes"])
    identifiers.extend(command["id"] for command in manifest["build"]["commands"])
    for suite in validation["testSuites"]:
        identifiers.extend((suite["id"], suite["command"]["id"]))
    for scenario in validation["scenarios"]:
        identifiers.extend((scenario["id"], scenario["command"]["id"]))
    package = validation.get("package")
    if package:
        identifiers.append(package["buildCommand"]["id"])
        identifiers.extend(
            command["id"] for command in package["cleanInstall"]["commands"]
        )
    identifiers.extend(artifact["id"] for artifact in manifest["artifacts"])
    return identifiers


def command_values(manifest: dict) -> list[str]:
    validation = manifest["validation"]
    commands = list(manifest["toolchain"]["probes"])
    commands.extend(manifest["build"]["commands"])
    commands.extend(suite["command"] for suite in validation["testSuites"])
    commands.extend(scenario["command"] for scenario in validation["scenarios"])
    package = validation.get("package")
    if package:
        commands.append(package["buildCommand"])
        commands.extend(package["cleanInstall"]["commands"])

    values = [manifest["build"]["buildDirectory"]]
    for command in commands:
        values.append(command["executable"])
        values.extend(command["arguments"])
        for field in ("workingDirectory", "capture"):
            if field in command:
                values.append(command[field])
    return values


def contract_errors(manifest: dict) -> list[str]:
    errors = []
    identifiers = manifest_ids(manifest)
    duplicates = sorted(
        identifier for identifier in set(identifiers) if identifiers.count(identifier) > 1
    )
    if duplicates:
        errors.append(f"duplicate IDs: {', '.join(duplicates)}")

    templates = {
        match.group(1)
        for value in command_values(manifest)
        for match in TEMPLATE_PATTERN.finditer(value)
    }
    unknown_templates = sorted(templates - ALLOWED_TEMPLATES)
    if unknown_templates:
        errors.append(f"unknown templates: {', '.join(unknown_templates)}")
    return errors


def main() -> int:
    schema_paths = sorted(SCHEMA_DIRECTORY.glob("*.schema.json"))
    manifest_paths = sorted(ROOT.glob(MANIFEST_PATTERN))
    if not schema_paths:
        print("No schemas found.", file=sys.stderr)
        return 1
    if not manifest_paths:
        print("No manifests found.", file=sys.stderr)
        return 1

    for schema_path in schema_paths:
        Draft202012Validator.check_schema(load_json(schema_path))
        print(f"Schema valid: {schema_path.relative_to(ROOT)}")

    manifest_schema = load_json(SCHEMA_DIRECTORY / "portpilot.schema.json")
    validator = Draft202012Validator(
        manifest_schema,
        format_checker=FormatChecker(),
    )
    manifests = []
    failures = []
    for manifest_path in manifest_paths:
        manifest = load_yaml(manifest_path)
        manifests.append(manifest)
        errors = sorted(
            validator.iter_errors(manifest),
            key=lambda error: tuple(str(part) for part in error.absolute_path),
        )
        custom_errors = contract_errors(manifest)
        failures.extend(format_error(manifest_path, error) for error in errors)
        failures.extend(f"{manifest_path}: {error}" for error in custom_errors)
        if not errors and not custom_errors:
            print(f"Manifest valid: {manifest_path.relative_to(ROOT)}")

    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1

    invalid_fixtures = []
    missing_revision = copy.deepcopy(manifests[0])
    del missing_revision["source"]["revision"]
    invalid_fixtures.append(("missing source revision", missing_revision))

    unknown_property = copy.deepcopy(manifests[0])
    unknown_property["project"]["unexpected"] = True
    invalid_fixtures.append(("unknown property", unknown_property))

    traversal_path = copy.deepcopy(manifests[0])
    traversal_path["evidence"]["directory"] = r"..\outside"
    invalid_fixtures.append(("path traversal", traversal_path))

    for name, fixture in invalid_fixtures:
        try:
            validator.validate(fixture)
        except ValidationError:
            print(f"Negative fixture rejected: {name}")
        else:
            print(f"Schema accepted invalid fixture: {name}", file=sys.stderr)
            return 1

    duplicate_id = copy.deepcopy(manifests[0])
    duplicate_id["artifacts"][0]["id"] = duplicate_id["build"]["commands"][0]["id"]
    unknown_template = copy.deepcopy(manifests[0])
    unknown_template["build"]["commands"][0]["arguments"].append("${typo}")
    for name, fixture in (
        ("duplicate ID", duplicate_id),
        ("unknown template", unknown_template),
    ):
        if contract_errors(fixture):
            print(f"Contract check rejected: {name}")
        else:
            print(f"Contract check accepted invalid fixture: {name}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
