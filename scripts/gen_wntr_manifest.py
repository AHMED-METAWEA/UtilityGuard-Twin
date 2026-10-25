#!/usr/bin/env python3
"""Write or check the WNTR API manifest of the water domain.

  python scripts/gen_wntr_manifest.py --write   regenerate the manifest from the installed WNTR
  python scripts/gen_wntr_manifest.py --check   fail if the committed manifest no longer matches

`--check` is part of `make ci`. All logic lives in `ug_water.wntr_api`; this script only does
the file handling and exit codes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ug_water import wntr_api

MANIFEST_PATH = (
    Path(__file__).resolve().parents[1]
    / "domains"
    / "water"
    / "src"
    / "ug_water"
    / wntr_api.MANIFEST_RESOURCE
)


def render(manifest: dict[str, object]) -> str:
    return json.dumps(manifest, indent=2, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--write", action="store_true", help="regenerate the manifest file"
    )
    mode.add_argument(
        "--check", action="store_true", help="verify the committed manifest"
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=MANIFEST_PATH,
        help="manifest file to write or check (default: the packaged one)",
    )
    args = parser.parse_args(argv)
    manifest_path: Path = args.manifest

    if args.write:
        manifest = wntr_api.generate()
        problems = wntr_api.verify(manifest)
        if problems:
            print("the freshly generated manifest does not verify:", file=sys.stderr)
            for problem in problems:
                print(f"  - {problem}", file=sys.stderr)
            return 1
        manifest_path.write_text(render(manifest), encoding="utf-8")
        print(
            f"wrote {manifest_path.name}: WNTR {manifest['wntr_version']}, "
            f"{wntr_api.symbol_count(manifest)} symbols"
        )
        return 0

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    problems = wntr_api.declared_matches_manifest(manifest) + wntr_api.verify(manifest)
    if problems:
        print(
            f"WNTR API manifest check FAILED ({len(problems)} problem(s)):",
            file=sys.stderr,
        )
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        print(
            "fix the code, or review and run: python scripts/gen_wntr_manifest.py --write",
            file=sys.stderr,
        )
        return 1
    print(
        f"WNTR API manifest OK: WNTR {manifest['wntr_version']}, "
        f"{wntr_api.symbol_count(manifest)} symbols verified"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
