"""The time axis shared by truth, telemetry and every consumer.

`Timebase` is what quality checks and detectors receive instead of a truth object (pitfall P-03:
the reference passed the whole truth series into the detector side just to read its time axis).

Samples sit at `start + i * step` for `i` in `0 .. n_ticks - 1`. Conversions from a time or an
offset to a tick are exact: a value that does not fall on a tick is an error, never silently rounded
(pitfall P-05: fault onsets landed one tick late in the reference).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any


@dataclass(frozen=True)
class Timebase:
    start: datetime
    step_seconds: int
    n_ticks: int

    def __post_init__(self) -> None:
        if not isinstance(self.start, datetime) or self.start.tzinfo is None:
            raise ValueError("start must be a timezone-aware datetime")
        object.__setattr__(self, "start", self.start.astimezone(UTC))
        if isinstance(self.step_seconds, bool) or not isinstance(self.step_seconds, int):
            raise TypeError("step_seconds must be an int")
        if isinstance(self.n_ticks, bool) or not isinstance(self.n_ticks, int):
            raise TypeError("n_ticks must be an int")
        if self.step_seconds <= 0:
            raise ValueError("step_seconds must be positive")
        if self.n_ticks <= 0:
            raise ValueError("n_ticks must be positive")

    def __len__(self) -> int:
        return self.n_ticks

    def ticks(self) -> range:
        return range(self.n_ticks)

    def time_at(self, tick: int) -> datetime:
        self._check_tick(tick)
        return self.start + timedelta(seconds=tick * self.step_seconds)

    def iso_at(self, tick: int) -> str:
        return self.time_at(tick).strftime("%Y-%m-%dT%H:%M:%SZ")

    def tick_at(self, when: datetime) -> int:
        """Tick for an exact time. Raises if `when` is not on a tick or outside the axis."""
        if when.tzinfo is None:
            raise ValueError("when must be a timezone-aware datetime")
        return self.tick_at_offset((when - self.start).total_seconds())

    def tick_at_offset(self, seconds: float) -> int:
        """Tick for an offset in seconds from `start`. Must be a whole number of steps."""
        if isinstance(seconds, bool) or not math.isfinite(seconds):
            raise ValueError(f"offset must be a finite number of seconds, got {seconds!r}")
        steps, remainder = divmod(seconds, self.step_seconds)
        if remainder != 0:
            raise ValueError(
                f"offset {seconds} s is not a whole number of {self.step_seconds} s steps"
            )
        tick = int(steps)
        self._check_tick(tick)
        return tick

    def to_dict(self) -> dict[str, Any]:
        return {
            "start": self.start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "step_seconds": self.step_seconds,
            "n_ticks": self.n_ticks,
        }

    def _check_tick(self, tick: int) -> None:
        if isinstance(tick, bool) or not isinstance(tick, int):
            raise TypeError("tick must be an int")
        if not 0 <= tick < self.n_ticks:
            raise ValueError(f"tick {tick} is outside 0..{self.n_ticks - 1}")
