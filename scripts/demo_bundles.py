"""Pack, verify and restore the recorded demo runs (the view bundles the API serves).

    python scripts/demo_bundles.py pack    [--views DIR] [--archive FILE]
    python scripts/demo_bundles.py verify  [--views DIR]
    python scripts/demo_bundles.py restore --archive FILE [--views DIR]

`pack` writes one .tar.gz (sorted members, fixed mtime: the same bundles give the same archive)
with a SHA256SUMS file inside. `verify` checks the checksums when SHA256SUMS is present and
loads every bundle through the API's own `RunStore` (every file validated against its contract,
no unexpected file), so a bundle that verifies is one the demo can serve. `restore` refuses an
archive with absolute or `..` paths, links or a bad checksum, then verifies.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIEWS = ROOT / "var/demo-runs/views"
ARCHIVE = ROOT / "var/demo-runs.tar.gz"
SUMS = "SHA256SUMS"


def _files(views: Path) -> list[Path]:
    return sorted(p for p in views.rglob("*") if p.is_file() and p.name != SUMS)


def _sums(views: Path) -> str:
    return "".join(
        f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(views).as_posix()}\n"
        for p in _files(views)
    )


def pack(views: Path, archive: Path) -> None:
    verify(views)
    (views / SUMS).write_text(_sums(views))
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for path in [views / SUMS, *_files(views)]:
            info = tarfile.TarInfo(path.relative_to(views).as_posix())
            info.size, info.mtime, info.mode = path.stat().st_size, 0, 0o644
            with path.open("rb") as handle:
                tar.addfile(info, handle)
    archive.parent.mkdir(parents=True, exist_ok=True)
    with gzip.GzipFile(archive, "wb", mtime=0) as out:
        out.write(buffer.getvalue())
    print(
        f"packed {len(_files(views))} files into {archive} ({archive.stat().st_size // 1024} KiB)"
    )


def verify(views: Path) -> None:
    from ug_api.runs import RunStore

    if not views.is_dir():
        sys.exit(f"no recorded runs in {views}")
    sums = views / SUMS
    if sums.exists() and sums.read_text() != _sums(views):
        sys.exit(f"checksums do not match {sums}")
    store = RunStore(views)
    runs = store.list()  # loads and validates every bundle
    if not runs:
        sys.exit(f"no recorded runs in {views}")
    for run in runs:
        bundle = store.load(run["run_id"])
        print(
            f"ok {run['run_id']} {run['scenario_id']}: {len(bundle.series)} series, "
            f"{len(bundle.incidents)} incidents, decision {'yes' if bundle.decision else 'no'}"
        )


def restore(archive: Path, views: Path) -> None:
    with tempfile.TemporaryDirectory() as folder:
        target = Path(folder)
        with tarfile.open(archive, "r:gz") as tar:
            for member in tar.getmembers():
                name = Path(member.name)
                if not member.isfile() or name.is_absolute() or ".." in name.parts:
                    sys.exit(f"refused archive member {member.name!r}")
            tar.extractall(target, filter="data")
        if not (target / SUMS).exists():
            sys.exit("the archive has no SHA256SUMS")
        verify(target)
        if views.exists():
            shutil.rmtree(views)
        shutil.copytree(target, views)
    print(f"restored into {views}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=["pack", "verify", "restore"])
    parser.add_argument("--views", type=Path, default=VIEWS)
    parser.add_argument("--archive", type=Path, default=ARCHIVE)
    args = parser.parse_args()
    if args.action == "pack":
        pack(args.views, args.archive)
    elif args.action == "verify":
        verify(args.views)
    else:
        restore(args.archive, args.views)


if __name__ == "__main__":
    main()
