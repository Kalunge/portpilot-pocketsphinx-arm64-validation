#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from portpilot.analysis.runner import analyze


def main() -> int:
    parser = argparse.ArgumentParser(description="Run PortPilot repository analysis.")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--repository", required=True, type=Path)
    parser.add_argument("--output-directory", required=True, type=Path)
    args = parser.parse_args()

    repository = args.repository.resolve()
    if not repository.is_dir():
        parser.error(f"repository does not exist: {repository}")
    summary = analyze(
        args.manifest.resolve(),
        repository,
        args.output_directory.resolve(),
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
