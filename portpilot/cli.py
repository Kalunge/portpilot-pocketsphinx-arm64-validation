from __future__ import annotations

import argparse
import sys
from pathlib import Path

from portpilot.orchestrator import (
    default_run_id,
    print_json,
    run_analysis_stage,
    run_pipeline,
    run_planning_stage,
    run_reporting_stage,
    status_summary,
    update_task_status,
)
from portpilot.execution.runner import execute_phase, execution_is_complete
from portpilot.state import RunState


def add_start_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--repository", required=True, type=Path)
    parser.add_argument("--runs-directory", type=Path, default=Path("runs"))
    parser.add_argument("--run-id")


def state_from_start_arguments(args: argparse.Namespace) -> RunState:
    run_id = args.run_id or default_run_id(args.manifest)
    return RunState.create_or_load(
        args.manifest.resolve(),
        args.repository.resolve(),
        args.runs_directory.resolve(),
        run_id,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="portpilot",
        description="Plan and coordinate evidence-backed Windows Arm ports.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze_parser = subparsers.add_parser("analyze")
    add_start_arguments(analyze_parser)

    run_parser = subparsers.add_parser("run")
    add_start_arguments(run_parser)

    for name in ("plan", "status", "report"):
        command_parser = subparsers.add_parser(name)
        command_parser.add_argument("--run-directory", required=True, type=Path)

    execute_parser = subparsers.add_parser("execute")
    execute_parser.add_argument("--run-directory", required=True, type=Path)
    execute_parser.add_argument(
        "--phase",
        required=True,
        choices=["baseline", "target"],
    )
    execute_parser.add_argument("--package", action="store_true")

    task_parser = subparsers.add_parser("task")
    task_parser.add_argument("--run-directory", required=True, type=Path)
    task_parser.add_argument("--id", required=True)
    task_parser.add_argument(
        "--set-status",
        required=True,
        choices=[
            "ready",
            "in-progress",
            "review",
            "done",
            "failed",
            "blocked",
        ],
    )
    return parser


def execute(args: argparse.Namespace) -> None:
    if args.command in {"analyze", "run"}:
        state = state_from_start_arguments(args)
        if args.command == "run":
            print_json(run_pipeline(state))
            return
        with state.lock():
            project = state.load_project()
            if project["stages"]["analysis"] != "done":
                run_analysis_stage(state)
            print_json(status_summary(state))
        return

    state = RunState.load(args.run_directory)
    if args.command == "status":
        with state.lock():
            print_json(status_summary(state))
    elif args.command == "execute":
        with state.lock():
            project = state.load_project()
            if project["stages"]["planning"] != "done":
                raise RuntimeError("planning must complete before execution")
            project["stages"]["execution"] = "in-progress"
            project["status"] = "running"
            state.save_project(project)
            (state.root / "report.json").unlink(missing_ok=True)
            try:
                summary = execute_phase(state, args.phase, args.package)
            except BaseException:
                project = state.load_project()
                project["stages"]["execution"] = "failed"
                project["status"] = "failed"
                state.save_project(project)
                raise
            project = state.load_project()
            complete = execution_is_complete(state)
            project["stages"]["execution"] = "done" if complete else "in-progress"
            project["status"] = "validating" if complete else "running"
            project["stages"]["reporting"] = "pending"
            state.save_project(project)
            print_json(summary)
    elif args.command == "plan":
        with state.lock():
            if state.load_project()["stages"]["planning"] != "done":
                run_planning_stage(state)
            print_json(status_summary(state))
    elif args.command == "report":
        with state.lock():
            report = run_reporting_stage(state)
            print_json(report)
    elif args.command == "task":
        print_json(update_task_status(state, args.id, args.set_status))


def main() -> int:
    parser = build_parser()
    try:
        execute(parser.parse_args())
    except (OSError, RuntimeError, ValueError) as error:
        print(f"portpilot: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
