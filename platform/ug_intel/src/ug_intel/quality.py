"""Domain-agnostic telemetry quality, all CALCULATED, formula_ref quality.score.v1.

Rules (all CALCULATED, `formula_ref` "quality.score.v1"):
- Q01 completeness and latency: value `None` -> Q01, status bad; delivery delay above 2 x step -> Q01, status suspect ("stale").
- Q02 physical range: value outside `ranges[sensor]` -> Q02, bad.
- Q04 flatline: the last 12 non-null values (window of one hour at 5-minute ticks; use `round(3600 / step)`) have max - min <= quantum -> Q04, suspect. Not raised before the window is full.
- Q08 model consistency (only when `expected` is given): residual r = value - expected; sigma = 1.4826 x median absolute deviation of r over the first 288 ticks with a floor of 2 x quantum; EWMA of r / sigma with alpha 0.02 started at 0; |EWMA| > 3 -> Q08, suspect.
- Score: ok 1.0, suspect 0.5, bad 0.0 (worst flag wins); flags sorted, unique.

Expected values are caller-supplied model expectations, never a truth object.
Calibration ignores missing readings among the first 288 ticks (not the first
288 valid readings). With no calibration residuals, sigma uses its floor.
Missing readings neither advance the non-null flatline window nor update EWMA.
No model flag is emitted on a missing tick. For steps above an hour the
flatline window has a minimum of one sample. All kinds use the same formulas;
the caller supplies their per-sensor physical ranges and quanta.
"""

from __future__ import annotations

import math
from collections import deque
from collections.abc import Mapping, Sequence
from decimal import Decimal
from statistics import median
from typing import Any

from ug_core.telemetry import TelemetrySeries


def _side_series(
    values: Sequence[float], count: int, name: str, *, non_negative: bool = False
) -> None:
    if len(values) != count or any(
        isinstance(v, bool) or not math.isfinite(v) or (non_negative and v < 0)
        for v in values
    ):
        raise ValueError(
            f"{name} must contain {count} finite {'non-negative ' if non_negative else ''}values"
        )


def assess(
    series: TelemetrySeries,
    kinds: Mapping[str, str],
    quanta: Mapping[str, float],
    ranges: Mapping[str, tuple[float, float]],
    delivered_delay_s: Mapping[str, Sequence[float]] | None = None,
    expected: Mapping[str, Sequence[float]] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """One v1 quality object per sensor/tick, containing no hidden fault metadata."""
    result: dict[str, list[dict[str, Any]]] = {}
    step, count = series.timebase.step_seconds, series.timebase.n_ticks
    window = max(1, round(3600 / step))
    for sensor, readings in series.readings.items():
        if not kinds[sensor]:
            raise ValueError(f"sensor {sensor} needs a kind")
        quantum = quanta[sensor]
        low, high = ranges[sensor]
        if isinstance(quantum, bool) or not math.isfinite(quantum) or quantum <= 0:
            raise ValueError(f"sensor {sensor} needs a positive finite quantum")
        if not math.isfinite(low) or not math.isfinite(high) or low > high:
            raise ValueError(f"sensor {sensor} needs a finite ordered range")
        delays = None if delivered_delay_s is None else delivered_delay_s[sensor]
        model = None if expected is None else expected[sensor]
        if delays is not None:
            _side_series(
                delays, count, f"delivered_delay_s[{sensor}]", non_negative=True
            )
        sigma = 2 * quantum
        if model is not None:
            _side_series(model, count, f"expected[{sensor}]")
            calibration = [
                v - model[t] for t, v in enumerate(readings[:288]) if v is not None
            ]
            if calibration:
                center = median(calibration)
                sigma = max(
                    sigma, 1.4826 * median(abs(r - center) for r in calibration)
                )
        history: deque[float] = deque(maxlen=window)
        ewma = 0.0
        quality = []
        for tick, value in enumerate(readings):
            flags: set[str] = set()
            score = 1.0
            if value is None:
                flags.add("Q01")
                score = 0.0
            if delays is not None and delays[tick] > 2 * step:
                flags.add("Q01")
                score = min(score, 0.5)
            if value is not None:
                if value < low or value > high:
                    flags.add("Q02")
                    score = 0.0
                history.append(value)
                # Decimal spellings preserve the inclusive quantum boundary:
                # float(20.01) - float(20.00) is slightly greater than .01.
                if len(history) == window and Decimal(str(max(history))) - Decimal(
                    str(min(history))
                ) <= Decimal(str(quantum)):
                    flags.add("Q04")
                    score = min(score, 0.5)
                if model is not None:
                    ewma = 0.02 * ((value - model[tick]) / sigma) + 0.98 * ewma
                    if abs(ewma) > 3:
                        flags.add("Q08")
                        score = min(score, 0.5)
            quality.append(
                {
                    "status": {1.0: "ok", 0.5: "suspect", 0.0: "bad"}[score],
                    "score": score,
                    "flags": sorted(flags),
                    "label": "CALCULATED",
                    "formula_ref": "quality.score.v1",
                }
            )
        result[sensor] = quality
    return result
