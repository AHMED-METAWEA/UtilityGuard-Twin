"""Generate hash-free development constraints from the container's runtime lock.

Run without arguments to regenerate constraints/runtime.txt, or with --check to
print a unified diff and exit 1 on drift. Malformed input or I/O errors exit 2.
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEADER = (
    "# Generated from deploy/requirements-api.lock by scripts/gen_constraints.py.\n"
    "# Do not edit by hand.\n"
)
_PIN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[^\]]*\])?==([^\s;\\]+)")


def read_lock(path: Path) -> dict[str, str]:
    """Read exact pins, skipping comments, blank lines and --hash= lines."""
    pins: dict[str, str] = {}
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith(("#", "--hash=")):
            continue
        if line.startswith("-"):
            raise ValueError(
                f"{path}:{number}: option lines are not supported: {line!r}"
            )
        match = _PIN.match(line)
        if match is None:
            raise ValueError(f"{path}:{number}: not an exact pin: {line!r}")
        name = re.sub(r"[-_.]+", "-", match.group(1)).lower()
        version = match.group(2)
        if name in pins and pins[name] != version:
            raise ValueError(f"{path}:{number}: conflicting pins for {name}")
        pins[name] = version
    if not pins:
        raise ValueError(f"{path}: no pinned package found")
    return pins


def generate(lock: Path) -> str:
    """Render one pin per normalized project name in deterministic order."""
    pins = read_lock(lock)
    return HEADER + "".join(f"{name}=={pins[name]}\n" for name in sorted(pins))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--lock", type=Path, default=ROOT / "deploy/requirements-api.lock"
    )
    parser.add_argument("--output", type=Path, default=ROOT / "constraints/runtime.txt")
    args = parser.parse_args(argv)
    try:
        expected = generate(args.lock)
        if args.check:
            actual = (
                args.output.read_text(encoding="utf-8") if args.output.exists() else ""
            )
            if actual != expected:
                sys.stdout.writelines(
                    difflib.unified_diff(
                        actual.splitlines(keepends=True),
                        expected.splitlines(keepends=True),
                        fromfile=str(args.output),
                        tofile="generated constraints",
                    )
                )
                return 1
        else:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(expected, encoding="utf-8")
    except (OSError, ValueError) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
