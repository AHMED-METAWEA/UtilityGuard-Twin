"""Argument parsing, output and exit codes for the ug command."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from ug_cli import __version__, fetch_geometry
from ug_cli.doctor import run_doctor
from ug_cli.export import export_command
from ug_cli.run import run_command


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ug")
    parser.add_argument("--version", action="version", version=f"ug {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser("doctor", help="check the local environment")
    doctor.add_argument("--json", action="store_true", help="emit a JSON report")
    doctor.add_argument(
        "--root", type=Path, help="repository root containing contracts/v1"
    )
    run = commands.add_parser(
        "run", help="simulate a scenario and write its run bundle"
    )
    run.add_argument("scenario", help="water preset id or JSON scenario path")
    run.add_argument("--network", choices=("procedural", "osm"), default="procedural")
    run.add_argument("--tier", choices=("lite", "standard", "full"), default="lite")
    run.add_argument("--seed", type=int)
    run.add_argument("--store", type=Path)
    run.add_argument("--assumptions", type=Path)
    run.add_argument("--duration-hours", type=float)
    export = commands.add_parser("export", help="export an operator replay bundle")
    export.add_argument("run_id")
    export.add_argument("--store", type=Path, required=True)
    export.add_argument("--out", type=Path, required=True)
    fetch_geometry.add_parser(commands)
    for command, milestone in (
        ("reproduce", "M4"),
        ("eval", "M5"),
        ("import", "M1"),
    ):
        stub = commands.add_parser(
            command, help=f"planned for Spec milestone {milestone}"
        )
        stub.set_defaults(milestone=milestone)
    args = parser.parse_args(argv)
    if args.command == "export":
        return export_command(args)
    if args.command == "run":
        return run_command(args)
    if args.command == "fetch-geometry":
        return fetch_geometry.run(args)
    if args.command != "doctor":
        print(
            f"ug {args.command}: not implemented yet "
            f"(planned for Spec milestone {args.milestone})",
            file=sys.stderr,
        )
        return 2
    results = run_doctor(args.root)
    counts = {
        status: sum(result.status == status for result in results)
        for status in ("ok", "warn", "fail")
    }
    ok = counts["fail"] == 0
    if args.json:
        print(
            json.dumps(
                {
                    "schema_version": "1",
                    "ok": ok,
                    "counts": counts,
                    "checks": [asdict(result) for result in results],
                },
                allow_nan=False,
            )
        )
    else:
        for result in results:
            prefix = "FAIL" if result.status == "fail" else result.status
            print(f"[{prefix}] {result.name}: {result.detail}")
        print(
            f"Summary: {counts['ok']} ok, {counts['warn']} warn, {counts['fail']} fail"
        )
    return 0 if ok else 1
