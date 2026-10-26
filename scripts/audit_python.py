"""Python dependency audit (task T-B1-002): known vulnerabilities in the exact versions we install.

For every package version it is given, this asks PyPI's JSON API
(`https://pypi.org/pypi/<name>/<version>/json`, field `vulnerabilities`) whether an advisory is
known. That field is PyPI's feed of the Python Packaging Advisory Database and OSV, the same
source `pip-audit` reads by default. Standard library only: no new dependency.

Usage:
    python scripts/audit_python.py [--lock FILE]... [--installed] [--ignore FILE]

    --lock FILE    every `name==version` line of a pip requirements file (for example the
                   hash-pinned runtime lock of the container). A line that is not an exact pin,
                   or an option line other than `--hash=` (an include, a constraint, an
                   editable, an index), is an error: a lock must say exactly what is installed.
    --installed    every distribution installed in this interpreter's environment, except local
                   installs (editable or `file://`, such as this repository's own packages), which
                   are listed as skipped.
    --local NAME   a package of this repository (repeatable): skipped wherever it appears.
    --ignore FILE  accepted advisories, one per line: `<id> until <YYYY-MM-DD> <reason>`. An entry
                   past its date no longer hides the advisory. Blank lines and `#` comments are
                   allowed; anything else is an error.

Exit codes: 0 no known vulnerability; 1 at least one; 2 the audit could not be completed (PyPI
unreachable after retries, a package that is not on PyPI and not a local install, a malformed
lock or ignore file). It fails closed: a package without an answer is never reported as clean.

It needs network access to pypi.org, so it is not part of `make ci` (which runs offline); hosted
CI runs it as the `audit` job (`make audit-python`).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date
from importlib import metadata
from pathlib import Path
from typing import Any

PYPI = "https://pypi.org/pypi/{name}/{version}/json"
USER_AGENT = (
    "UtilityGuard-Twin-audit/1 (+https://github.com/AHMED-METAWEA/UtilityGuard-Twin)"
)
TIMEOUT_S = 30
ATTEMPTS = 3
WORKERS = 8

_PIN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[^\]]*\])?==([^\s;\\]+)")
_IGNORE = re.compile(r"^(\S+)\s+until\s+(\d{4}-\d{2}-\d{2})\s+(\S.*)$")


class AuditError(Exception):
    """The audit could not be completed (exit code 2)."""


class NotOnPyPI(AuditError):
    """PyPI has no such project or version."""


def normalize(name: str) -> str:
    """PEP 503 name normalization (`PyYAML` and `pyyaml` are the same project)."""
    return re.sub(r"[-_.]+", "-", name).lower()


@dataclass(frozen=True, order=True)
class Package:
    name: str
    version: str
    origin: str


@dataclass(frozen=True)
class Advisory:
    id: str
    aliases: tuple[str, ...]
    fixed_in: tuple[str, ...]


@dataclass
class Report:
    vulnerable: dict[Package, list[Advisory]] = field(default_factory=dict)
    ignored: dict[Package, list[tuple[Advisory, str]]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    checked: list[Package] = field(default_factory=list)
    skipped_local: list[str] = field(default_factory=list)


def read_lock(path: Path) -> list[Package]:
    """Exact pins of a requirements file; option lines (`--hash`) and comments are skipped."""
    packages: list[Package] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise AuditError(f"cannot read the lock {path}: {exc}") from exc
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("--hash="):
            continue
        if line.startswith("-"):
            # An include, a constraint, an editable or an index option would hide or change what
            # is installed: a lock lists exact pins and their hashes, nothing else.
            raise AuditError(
                f"{path}:{number}: option lines are not supported in a lock: {line!r}"
            )
        match = _PIN.match(line)
        if match is None:
            raise AuditError(
                f"{path}:{number}: not an exact pin (name==version): {line!r}"
            )
        packages.append(Package(normalize(match.group(1)), match.group(2), str(path)))
    if not packages:
        raise AuditError(f"{path}: no pinned package found")
    return packages


def _is_local(dist: metadata.Distribution) -> bool:
    """Editable or `file://` installs (PEP 610 `direct_url.json`) are this repository's code."""
    text = dist.read_text("direct_url.json")
    if not text:
        return False
    try:
        url = json.loads(text).get("url", "")
    except ValueError:
        return False
    return isinstance(url, str) and url.startswith("file://")


def installed_packages(
    distributions: Iterable[metadata.Distribution] | None = None,
) -> tuple[list[Package], list[str]]:
    packages: dict[str, Package] = {}
    local: set[str] = set()
    for dist in metadata.distributions() if distributions is None else distributions:
        raw_name = dist.metadata["Name"] if dist.metadata else None
        if not raw_name:
            continue
        name = normalize(raw_name)
        if _is_local(dist):
            local.add(name)
            continue
        packages[name] = Package(name, dist.version, "installed")
    # An editable install can leave a second record (an old `.egg-info`) without
    # `direct_url.json`: a name seen as local once is local.
    kept = [package for name, package in packages.items() if name not in local]
    return sorted(kept), sorted(local)


def read_ignores(path: Path, today: date) -> tuple[dict[str, str], list[str]]:
    """Active accepted advisories (id to reason) and the notes about expired ones."""
    active: dict[str, str] = {}
    notes: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise AuditError(f"cannot read the ignore file {path}: {exc}") from exc
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = _IGNORE.match(line)
        if match is None:
            raise AuditError(
                f"{path}:{number}: expected '<id> until <YYYY-MM-DD> <reason>', got {line!r}"
            )
        advisory, until, reason = match.groups()
        try:
            expires = date.fromisoformat(until)
        except ValueError as exc:
            raise AuditError(f"{path}:{number}: {until!r} is not a date") from exc
        if expires < today:
            notes.append(
                f"ignore entry for {advisory} expired on {until}; it no longer applies"
            )
            continue
        active[advisory] = reason
    return active, notes


def fetch_json(url: str) -> dict[str, Any]:
    """GET a PyPI JSON document, with retries on network errors, 429 and 5xx."""
    last: Exception | None = None
    for attempt in range(ATTEMPTS):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
                data = json.load(response)
            if not isinstance(data, dict):
                raise AuditError(f"{url}: PyPI did not return a JSON object")
            return data
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise NotOnPyPI(f"{url}: not on PyPI (HTTP 404)") from exc
            if exc.code != 429 and exc.code < 500:
                raise AuditError(f"{url}: HTTP {exc.code}") from exc
            last = exc
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            last = exc
        time.sleep(2**attempt)
    raise AuditError(f"{url}: no answer after {ATTEMPTS} attempts ({last})")


def advisories(data: dict[str, Any], url: str) -> list[Advisory]:
    raw = data.get("vulnerabilities")
    if not isinstance(raw, list):
        raise AuditError(f"{url}: the answer has no 'vulnerabilities' list")
    found: list[Advisory] = []
    for entry in raw:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            raise AuditError(f"{url}: an advisory without an id: {entry!r}")
        if entry.get("withdrawn"):
            continue
        found.append(
            Advisory(
                entry["id"],
                tuple(sorted(str(a) for a in entry.get("aliases") or [])),
                tuple(str(v) for v in entry.get("fixed_in") or []),
            )
        )
    return merge_aliases(found)


def merge_aliases(found: list[Advisory]) -> list[Advisory]:
    """One entry per vulnerability: advisories that share an id or an alias are merged.

    PyPI lists the same issue under several ids (a PYSEC id and a GHSA id that alias the same
    CVE); counting each would inflate the number of vulnerabilities.
    """
    groups: list[tuple[set[str], set[str]]] = []  # (ids and aliases, fixed-in versions)
    for advisory in found:
        names = {advisory.id, *advisory.aliases}
        fixed = set(advisory.fixed_in)
        touching = [group for group in groups if group[0] & names]
        for group in touching:
            names |= group[0]
            fixed |= group[1]
            groups.remove(group)
        groups.append((names, fixed))
    merged = []
    for names, fixed in groups:
        cves = sorted(n for n in names if n.startswith("CVE-"))
        primary = cves[0] if cves else sorted(names)[0]
        merged.append(
            Advisory(primary, tuple(sorted(names - {primary})), tuple(sorted(fixed)))
        )
    return sorted(merged, key=lambda advisory: advisory.id)


def audit(
    packages: list[Package],
    ignores: dict[str, str],
    fetch: Callable[[str], dict[str, Any]] | None = None,
) -> Report:
    get = fetch_json if fetch is None else fetch
    report = Report()
    unique = sorted({(p.name, p.version): p for p in packages}.values())

    def one(package: Package) -> tuple[Package, list[Advisory] | None, str | None]:
        url = PYPI.format(name=package.name, version=package.version)
        try:
            return package, advisories(get(url), url), None
        except AuditError as exc:
            return (
                package,
                None,
                f"{package.name}=={package.version} ({package.origin}): {exc}",
            )

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        results = list(pool.map(one, unique))
    for package, found, error in results:
        if error is not None:
            report.errors.append(error)
            continue
        report.checked.append(package)
        for advisory in found or []:
            names = {advisory.id, *advisory.aliases}
            accepted = next((ignores[n] for n in sorted(names) if n in ignores), None)
            if accepted is None:
                report.vulnerable.setdefault(package, []).append(advisory)
            else:
                report.ignored.setdefault(package, []).append((advisory, accepted))
    return report


def render(report: Report, notes: list[str]) -> list[str]:
    lines: list[str] = []
    for package in sorted(report.vulnerable):
        for advisory in report.vulnerable[package]:
            aliases = ", ".join(advisory.aliases) or "no alias"
            fixed = ", ".join(advisory.fixed_in) or "no fixed release listed"
            lines.append(
                f"VULNERABLE {package.name}=={package.version} ({package.origin}): "
                f"{advisory.id} ({aliases}); fixed in {fixed}"
            )
    for package in sorted(report.ignored):
        for advisory, reason in report.ignored[package]:
            lines.append(
                f"IGNORED {package.name}=={package.version}: {advisory.id} (accepted: {reason})"
            )
    lines.extend(f"ERROR {error}" for error in sorted(report.errors))
    lines.extend(f"NOTE {note}" for note in notes)
    if report.skipped_local:
        lines.append("SKIPPED local installs: " + ", ".join(report.skipped_local))
    count = sum(len(v) for v in report.vulnerable.values())
    lines.append(
        f"Summary: {len(report.checked)} package versions checked against PyPI, "
        f"{count} known vulnerabilities, {len(report.errors)} errors"
    )
    return lines


def main(argv: list[str] | None = None, today: date | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--lock", type=Path, action="append", default=[])
    parser.add_argument("--installed", action="store_true")
    parser.add_argument("--ignore", type=Path)
    parser.add_argument(
        "--local",
        action="append",
        default=[],
        metavar="NAME",
        help="a package of this repository that may appear in a lock or freeze list",
    )
    args = parser.parse_args(argv)
    if not args.lock and not args.installed:
        parser.error("give at least one --lock FILE or --installed")
    try:
        packages: list[Package] = []
        for lock in args.lock:
            packages.extend(read_lock(lock))
        local: list[str] = []
        if args.installed:
            found, local = installed_packages()
            packages.extend(found)
        own = {normalize(name) for name in args.local}
        local = sorted(set(local) | {p.name for p in packages if p.name in own})
        packages = [p for p in packages if p.name not in own]
        ignores, notes = (
            read_ignores(args.ignore, today or date.today())
            if args.ignore
            else ({}, [])
        )
    except AuditError as exc:
        print(f"ERROR {exc}")
        return 2
    report = audit(packages, ignores)
    report.skipped_local = local
    for line in render(report, notes):
        print(line)
    if report.errors:
        return 2
    return 1 if report.vulnerable else 0


if __name__ == "__main__":
    sys.exit(main())
