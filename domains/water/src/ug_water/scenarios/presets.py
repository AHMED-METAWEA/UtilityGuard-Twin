"""Packaged scenario data for the seed-1 procedural F0 fixture (temporary lite).

Demand flags, timing and fault magnitudes are ASSUMPTIONs, not field observations.
Loading does not build a network or run hydraulics. Contract and element checks
are offline tests; hydraulic validation remains a separate engine responsibility.
"""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any


def list_presets() -> tuple[str, ...]:
    """Return the packaged scenario identifiers in sorted order."""
    return tuple(
        sorted(
            item.name.removesuffix(".json")
            for item in files("ug_water.scenarios").joinpath("presets").iterdir()
            if item.is_file() and item.name.endswith(".json")
        )
    )


def load_preset(preset_id: str) -> dict[str, Any]:
    """Return independent nested data; unknown ids raise KeyError with known ids."""
    known = list_presets()
    if preset_id not in known:
        raise KeyError(f"Unknown preset {preset_id!r}; known ids: {', '.join(known)}")
    # Parsing afresh gives a deep copy without retaining mutable shared state.
    result: dict[str, Any] = json.loads(
        files("ug_water.scenarios")
        .joinpath("presets", f"{preset_id}.json")
        .read_text(encoding="utf-8")
    )
    return result
