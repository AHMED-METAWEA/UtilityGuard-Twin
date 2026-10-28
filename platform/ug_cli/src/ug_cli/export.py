"""Export a recorded run through its domain's privileged measurement bridge."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from ug_core.registry import discover
from ug_core.store.run import RunStore
from ug_intel.detect.cusum import detect
from ug_intel.detect.incident import incident_from
from ug_intel.quality import assess

from ug_cli.run import _root, _validator


def export_run(run_id: str, store: Path, out: Path) -> Path:
    """Publish a validated, byte-stable D-07 view; never overwrite different data."""
    root = _root()
    source = RunStore(store)
    manifest = source.verify(run_id)
    adapter = discover().get("water")
    hook = getattr(adapter, "export_view", None)
    if not callable(hook):
        raise ValueError("water adapter has no recorded-view export capability")
    view = hook(source, run_id, root / "assumptions")
    telemetry = view["telemetry"]
    quality = assess(
        telemetry,
        view["kinds"],
        view["quanta"],
        view["ranges"],
        view["delays"],
        view["expected"],
    )
    readings = view["serialize"](telemetry, view["asset"], view["delays"], quality)
    result = detect(telemetry.readings, view["expected"], quality, view["quanta"])
    incident = incident_from(result, view["kinds"], quality, run_id, view["zones"])
    # This is the view manifest, not the restricted reproducibility manifest.
    # Keep no scenario injection configuration or restricted output hashes.
    public_manifest = manifest.to_dict()
    public_manifest["config"]["faults"] = []
    public_manifest["config"]["cross_domain_inputs"] = []
    public_manifest["output_hashes"] = {}
    payloads: dict[str, tuple[str, Any]] = {
        "manifest.json": ("run-manifest", public_manifest),
        "network.json": ("network-view", view["network"]),
        "readings.json": ("telemetry-reading", readings),
        "incidents.json": ("incident", [] if incident is None else [incident]),
    }
    for sensor, values in sorted(telemetry.readings.items()):
        expected = view["expected"][sensor]
        residual = [
            None if value is None else value - expected[tick]
            for tick, value in enumerate(values)
        ]
        for kind, label, series_values in (
            ("sensor", "SENSOR_SIM", values),
            ("expectation", "MODEL", expected),
            ("residual", "CALCULATED", residual),
        ):
            series_id = f"{sensor}.{kind}"
            payload = dict(
                schema_version="1",
                series_id=series_id,
                run_id=run_id,
                kind=kind,
                element=view["elements"][sensor],
                quantity=view["kinds"][sensor],
                unit="L/s" if view["kinds"][sensor] == "flow" else "m",
                label=label,
                start=telemetry.timebase.iso_at(0),
                step_seconds=telemetry.timebase.step_seconds,
                values=list(series_values),
            )
            if kind == "expectation":
                payload["version"] = "expectation_v1"
            if kind == "residual":
                payload["formula_ref"] = "residual.reading_minus_expectation.v1"
            payloads[f"series/{series_id}.json"] = ("time-series", payload)
    # D2 alone does not estimate physical exposure rates. Do not invent costs or
    # a decision from a detector score; the baseline has no decision payload.
    encoded = {}
    validators = {
        name: _validator(root, name)
        for name in {contract for contract, _ in payloads.values()}
    }
    for filename, (contract, payload) in sorted(payloads.items()):
        for item in payload if isinstance(payload, list) else [payload]:
            validators[contract].validate(item)
        encoded[filename] = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    out.mkdir(parents=True, exist_ok=True)
    destination = out / run_id
    if destination.exists() or destination.is_symlink():
        if destination.is_symlink() or not destination.is_dir():
            raise ValueError("unsafe existing export")
        existing = {
            p.relative_to(destination).as_posix(): p.read_bytes()
            for p in destination.rglob("*")
            if p.is_file() and not p.is_symlink()
        }
        if any(p.is_symlink() for p in destination.rglob("*")) or existing != encoded:
            raise ValueError("existing export differs; choose another output directory")
        return destination
    stage = Path(tempfile.mkdtemp(prefix=".export-", dir=out.parent))
    try:
        for filename, data in encoded.items():
            path = stage / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        os.rename(stage, destination)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return destination


def export_command(args: argparse.Namespace) -> int:
    try:
        print(export_run(args.run_id, args.store, args.out))
        return 0
    except Exception as exc:
        print(f"ug export: {exc}", file=sys.stderr)
        return 1
