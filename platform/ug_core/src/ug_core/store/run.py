"""Immutable, content-addressed runs with fail-closed consumer access.

Assemble a RunDraft using new(), write_table() and the privileged bundle writer,
then publish once with write(). All files and the manifest are staged together
in a hidden sibling directory. Published runs cannot be extended or overwritten;
assemble the complete output set before publication. Repeating identical output
is a verified no-op, including when two processes publish concurrently.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pyarrow as pa  # type: ignore[import-untyped]

from ug_core.canonical import canonical_json
from ug_core.manifest import Manifest
from ug_core.store.hashing import table_hash
from ug_core.store.layout import StoreError, run_id, run_path, table_key
from ug_core.store.tables import prepare, query_rows, read_parquet, write_parquet


@dataclass
class RunDraft:
    """In-memory output set; not readable through the consumer interface."""

    manifest: Manifest
    _tables: dict[str, pa.Table] = field(default_factory=dict, init=False, repr=False)

    def _add(self, name: str, table: pa.Table) -> None:
        if name in self._tables:
            raise StoreError(f"duplicate output: {name}")
        prepared = prepare(name, table, internal=True)
        table_hash(prepared, table_key(name, internal=True))
        self._tables[name] = prepared


@dataclass(frozen=True)
class RunReader:
    """Verified manifest and non-privileged rows; every read re-verifies the files."""

    _store: RunStore = field(repr=False)
    _identifier: str
    manifest: Manifest

    def read_table(
        self, name: str, ticks: tuple[int, int] | None = None
    ) -> list[dict[str, Any]]:
        table_key(name)  # Refuse restricted names before looking at any file.
        current = self._store.verify(self._identifier)
        if current != self.manifest:
            raise StoreError("run changed after open")
        if name not in current.output_hashes:
            raise StoreError(f"missing output: {name}")
        try:
            return query_rows(
                run_path(self._store.root, self._identifier) / f"{name}.parquet",
                name,
                ticks,
            )
        except StoreError:
            raise
        except Exception as exc:
            raise StoreError(f"cannot read {name}: {exc}") from exc


class RunStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def new(self, manifest: Manifest) -> RunDraft:
        return RunDraft(manifest)

    def write_table(self, run: RunDraft, name: str, table: pa.Table) -> None:
        """Add a Spec 11.2 consumer table to an unpublished draft."""
        table_key(name)
        try:
            run._add(name, table)
        except StoreError:
            raise
        except Exception as exc:
            raise StoreError(f"invalid table {name}: {exc}") from exc

    def write(self, run: RunDraft) -> str:
        """Atomically publish a complete draft; never replace a published run."""
        identifier = run_id(run.manifest)
        destination = run_path(self.root, identifier)
        # Validate everything before creating even the root or a staging folder.
        try:
            if "truth" not in run._tables:
                raise StoreError("missing required bundle")
            outputs = {}
            for name, table in run._tables.items():
                prepare(name, table, internal=True)
                outputs[name] = table_hash(table, table_key(name, internal=True))
            manifest = run.manifest.with_output_hashes(outputs)
        except StoreError:
            raise
        except Exception as exc:
            raise StoreError(f"invalid output: {exc}") from exc
        if destination.exists() or destination.is_symlink():
            self._check_existing(identifier, manifest)
            return identifier
        self.root.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix=f".{identifier}-", dir=self.root))
        try:
            for name, table in sorted(run._tables.items()):
                write_parquet(table, stage / f"{name}.parquet")
            (stage / "manifest.json").write_text(
                canonical_json(manifest.to_dict()), encoding="ascii"
            )
            try:
                os.replace(stage, destination)
            except OSError:
                if destination.exists():
                    self._check_existing(identifier, manifest)
                else:
                    raise
        except StoreError:
            raise
        except Exception as exc:
            raise StoreError(f"cannot publish {identifier}: {exc}") from exc
        finally:
            if stage.exists():
                shutil.rmtree(stage)
        return identifier

    def _check_existing(self, identifier: str, manifest: Manifest) -> None:
        existing = self.verify(identifier)
        if existing != manifest:
            names = sorted(
                name
                for name in existing.output_hashes.keys()
                | manifest.output_hashes.keys()
                if existing.output_hashes.get(name) != manifest.output_hashes.get(name)
            )
            raise StoreError(
                "same manifest, different outputs: the run is not deterministic; "
                + ", ".join(names or ["manifest"])
            )

    def verify(self, identifier: str) -> Manifest:
        """Validate canonical manifest, folder identity, exact file set and every hash."""
        try:
            directory = run_path(self.root, identifier)
            if directory.is_symlink() or not directory.is_dir():
                raise StoreError(f"missing or unsafe run folder: {identifier}")
            path = directory / "manifest.json"
            if path.is_symlink():
                raise StoreError("unsafe manifest")
            text = path.read_text(encoding="ascii")
            payload = json.loads(text)
            manifest = Manifest(**payload)
            if canonical_json(manifest.to_dict()) != text:
                raise StoreError("manifest must contain exactly its canonical fields")
            if run_id(manifest) != identifier:
                raise StoreError("manifest run_id does not match its folder")
            if "truth" not in manifest.output_hashes:
                raise StoreError("missing required bundle hash")
            expected = {"manifest.json"} | {
                f"{name}.parquet" for name in manifest.output_hashes
            }
            actual = {p.name for p in directory.iterdir()}
            if actual != expected:
                raise StoreError(
                    f"unexpected or missing files: {sorted(actual ^ expected)}"
                )
            for name, digest in manifest.output_hashes.items():
                key = table_key(name, internal=True)
                path = directory / f"{name}.parquet"
                if path.is_symlink() or not path.is_file():
                    raise StoreError(f"missing or unsafe output: {name}")
                table = read_parquet(path)
                prepare(name, table, internal=True)
                if table_hash(table, key) != digest:
                    raise StoreError(f"output hash mismatch: {name}")
            return manifest
        except StoreError:
            raise
        except Exception as exc:
            raise StoreError(f"cannot verify {identifier}: {exc}") from exc

    def open(self, identifier: str) -> RunReader:
        return RunReader(self, identifier, self.verify(identifier))
