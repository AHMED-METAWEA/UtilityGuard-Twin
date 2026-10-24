"""Hypothetical demand zones.

Everything in this file is an ASSUMPTION about a fictitious utility: the
patterns are illustrative shapes, not measured demand from any real city.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np

ZONE_NAMES = ("gov", "res", "com")

# Hourly multipliers (index 0 = 00:00-01:00 local). Illustrative only.
ZONE_HOURLY: dict[str, tuple[float, ...]] = {
    "gov": (
        0.15, 0.12, 0.12, 0.12, 0.15, 0.25, 0.50, 0.90, 1.35, 1.60, 1.65, 1.60,
        1.35, 1.45, 1.55, 1.50, 1.30, 0.90, 0.55, 0.35, 0.25, 0.20, 0.18, 0.16,
    ),
    "res": (
        0.35, 0.30, 0.28, 0.28, 0.32, 0.50, 1.10, 1.75, 1.40, 1.00, 0.85, 0.85,
        0.90, 0.85, 0.85, 0.95, 1.20, 1.55, 1.80, 1.60, 1.30, 1.00, 0.70, 0.50,
    ),
    "com": (
        0.20, 0.18, 0.18, 0.18, 0.20, 0.25, 0.40, 0.70, 1.20, 1.60, 1.75, 1.80,
        1.70, 1.65, 1.60, 1.50, 1.25, 0.95, 0.70, 0.50, 0.35, 0.28, 0.24, 0.20,
    ),
}

# Hypothetical peak demand per zone, L/s, spread across that zone's junctions.
ZONE_PEAK_LPS: dict[str, float] = {"gov": 18.0, "res": 24.0, "com": 22.0}

# Holiday assumption: government-district demand falls by 40% by default.
HOLIDAY_GOV_FACTOR = 0.6

# Per-junction deterministic variation so the network is not perfectly uniform.
def node_demand_factor(node_index: int) -> float:
    return 0.85 + 0.06 * (node_index % 5)


@dataclass(frozen=True)
class DemandProfile:
    """Time-varying demand multipliers for one hypothetical scenario."""

    hours: np.ndarray
    zone_multipliers: dict[str, np.ndarray]

    def value_at_hour(self, zone: str, hour: float, tick: int) -> float:
        return float(self.zone_multipliers[zone][tick])


def hourly_curve(zone: str, holiday: bool) -> np.ndarray:
    curve = np.asarray(ZONE_HOURLY[zone], dtype=float)
    if holiday and zone == "gov":
        curve = curve * HOLIDAY_GOV_FACTOR
    return curve


def multiplier_series(
    zone: str,
    ticks: int,
    timestep_minutes: int,
    start_hour: float,
    holiday: bool,
    heatwave: float,
    zone_multiplier: float,
    start_time: datetime | None = None,
) -> list[float]:
    """Multipliers for `ticks` samples starting at absolute scenario `start_hour`.

    WNTR patterns are anchored at the start of each (possibly chunked) run, so
    the runner passes the chunk offset here and gets a shifted list.
    """
    curve = hourly_curve(zone, holiday)
    hours = np.arange(ticks + 1, dtype=float) * (timestep_minutes / 60.0) + start_hour
    hod = np.mod(hours, 24.0)
    base = np.interp(hod, np.arange(24, dtype=float), curve, period=24.0)
    start_idx = hod[0]
    _ = start_idx
    values = base * heatwave * zone_multiplier
    return [round(float(v), 8) for v in values]
