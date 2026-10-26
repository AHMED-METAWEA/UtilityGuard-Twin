"""Synthetic demand and independent forecast, with versioned ASSUMPTION inputs.

Base demand is the provider's average m3/s; it is never re-estimated here.
Hourly raw profiles are normalized to mean one. Ramadan profile h00 is Iftar,
h01 is one hour after Iftar, etc.; interpolation wraps at midnight. Season,
weekend, holiday and heatwave factors multiply even on Ramadan days.

AR(1) sigma is the stationary standard deviation, phi is correlation per hydraulic
step. A stationary initial draw avoids burn-in. Gaussian errors are unbounded:
an unrealistically large sigma can produce negative demand and raises, never clips.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from ug_core import grammar
from ug_core.assumptions import AssumptionSet, load_assumptions
from ug_core.canonical import canonical_json, sha256_hex
from ug_core.evidence import EvidenceLabel
from ug_core.numeric import round_for_hash
from ug_core.rng import SeedStreams
from ug_core.timebase import Timebase

from ug_water.demand.calendar import DemandCalendar
from ug_water.network.model import Network


@dataclass(frozen=True, eq=False)
class DemandSeries:
    """Immutable m3/s at sorted junctions, with evidence and assumption provenance."""

    timebase: Timebase
    junction_ids: tuple[str, ...]
    values: NDArray[np.float64]
    label: EvidenceLabel
    assumption_set_hash: str

    def __post_init__(self) -> None:
        ids = tuple(self.junction_ids)
        if not ids or ids != tuple(sorted(set(ids))):
            raise ValueError("junction_ids must be non-empty, sorted and unique")
        for identifier in ids:
            grammar.require_identifier(identifier, "junction id")
        if not isinstance(self.label, EvidenceLabel) or self.label not in (
            EvidenceLabel.SIMULATION,
            EvidenceLabel.MODEL,
        ):
            raise ValueError("demand label must be SIMULATION or MODEL")
        if not grammar.is_sha256(self.assumption_set_hash):
            raise ValueError("assumption_set_hash must be a lower-case SHA-256")
        values = np.asarray(self.values, dtype=np.float64)
        if values.shape != (self.timebase.n_ticks, len(ids)):
            raise ValueError("demand values shape must be (n_ticks, n_junctions)")
        if not np.all(np.isfinite(values)) or np.any(values < 0):
            raise ValueError("demand values must be finite and non-negative")
        # Bytes-backed storage also prevents callers from re-enabling writeability.
        values = np.frombuffer(values.tobytes(), dtype=np.float64).reshape(values.shape)
        values.flags.writeable = False
        object.__setattr__(self, "junction_ids", ids)
        object.__setattr__(self, "values", values)

    def total_m3s(self) -> NDArray[np.float64]:
        """Per-tick totals; these retain this series' label and m3/s unit."""
        return self.values.sum(axis=1)

    def content_hash(self) -> str:
        return sha256_hex(
            canonical_json(
                {
                    "schema_version": "1",
                    "timebase": self.timebase.to_dict(),
                    "junction_ids": self.junction_ids,
                    "unit": "m3/s",
                    "values": np.asarray(
                        np.frompyfunc(round_for_hash, 1, 1)(self.values)
                    ).tolist(),
                    "label": self.label.value,
                    "assumption_set_hash": self.assumption_set_hash,
                }
            )
        )


@dataclass(frozen=True)
class _LocalAxis:
    """Shared local calendar arrays, computed once per public evaluation."""

    seconds: NDArray[np.int64]
    microsecond: int
    hours: NDArray[np.float64]
    months: NDArray[np.int64]
    weekend: NDArray[np.bool_]
    ramadan: NDArray[np.bool_]
    holidays: NDArray[np.bool_]
    heatwave: NDArray[np.bool_]

    def active(self, start: datetime, end: datetime) -> NDArray[np.bool_]:
        # Ceil each boundary relative to the axis' fixed fractional second. This
        # preserves subsecond half-open windows without floating epoch rounding.
        epoch = datetime(1970, 1, 1)
        first, last = start - epoch, end - epoch
        lower = (
            first.days * 86400 + first.seconds + (first.microseconds > self.microsecond)
        )
        upper = (
            last.days * 86400 + last.seconds + (last.microseconds > self.microsecond)
        )
        return (self.seconds >= lower) & (self.seconds < upper)


@dataclass(frozen=True)
class DemandModel:
    """Pure evaluations from one strict, immutable assumption set (uses its modes).

    Construct with ``DemandModel.from_file(path)``; explicit paths also work outside
    the repository. No implicit clock, random state, data download or config cache.
    """

    assumptions: AssumptionSet

    @classmethod
    def from_file(cls, path: str | Path) -> DemandModel:
        return cls(load_assumptions(path))

    def parameter(self, name: str, unit: str = "ratio") -> float:
        """Read an ASSUMPTION mode; retain full evidence in ``assumptions``."""
        try:
            entry = self.assumptions.assumptions[name]
        except KeyError:
            raise ValueError(f"missing demand assumption {name!r}") from None
        if entry.unit != unit:
            raise ValueError(f"{name}: expected unit {unit!r}, got {entry.unit!r}")
        return entry.distribution.mode

    def _positive(self, name: str) -> float:
        value = self.parameter(name)
        if self.assumptions.assumptions[name].distribution.min <= 0:
            raise ValueError(f"{name}: multiplier range must be positive")
        return value

    def pattern(self, land_use: str, *, ramadan: bool = False) -> NDArray[np.float64]:
        kind = "ramadan" if ramadan else "diurnal"
        prefix = f"demand_{kind}_{land_use}_h"
        if not any(name.startswith(prefix) for name in self.assumptions.assumptions):
            raise ValueError(f"unknown land use {land_use!r}: no {kind} pattern")
        values = np.array([self._positive(f"{prefix}{h:02d}") for h in range(24)])
        # Scale before summing, avoiding overflow for finite but large raw inputs.
        values /= values.max()
        values /= values.mean()
        values[-1] += 24.0 - values.sum()
        if not np.all(np.isfinite(values)) or np.any(values <= 0):
            raise ValueError(
                f"{land_use}: normalized pattern must be finite and positive"
            )
        values.flags.writeable = False
        return values

    def _axis(self, timebase: Timebase, calendar: DemandCalendar) -> _LocalAxis:
        offset = self.parameter("utc_offset_hours", "h")
        if not -24 < offset < 24:
            raise ValueError("utc_offset_hours must be between -24 and 24")
        shift = timedelta(hours=offset)
        seconds = (
            int(timebase.start.timestamp())
            + np.arange(timebase.n_ticks, dtype=np.int64) * timebase.step_seconds
            + shift.days * 86400
            + shift.seconds
        )
        days = seconds // 86400
        within_day = seconds % 86400
        # Algebraically within_day / 3600, but keep the original float operation
        # order: direct division changes bits (e.g. local 01:35) and demand values.
        hours = (
            within_day // 3600
            + (within_day // 60 % 60) / 60
            + (within_day % 60) / 3600
            + shift.microseconds / 3.6e9
        )
        months = days.astype("datetime64[D]").astype("datetime64[M]").astype(np.int64)
        epoch_day = date(1970, 1, 1).toordinal()
        return _LocalAxis(
            seconds,
            shift.microseconds,
            hours,
            months % 12,
            np.isin((days + 3) % 7, (4, 5)),  # Unix epoch was Thursday (weekday 3).
            np.isin(days, [day.toordinal() - epoch_day for day in calendar.ramadan]),
            np.isin(days, [day.toordinal() - epoch_day for day in calendar.holidays]),
            np.isin(days, [day.toordinal() - epoch_day for day in calendar.heatwave]),
        )

    def _validate_calendar(self, network: Network, calendar: DemandCalendar) -> None:
        zones = {zone.id for zone in network.zones}
        junctions = {junction.id for junction in network.junctions}
        for event in calendar.events:
            if event.zone_id not in zones:
                raise ValueError(
                    f"calendar event refers to unknown zone {event.zone_id!r}"
                )
        for fire in calendar.fire_flows:
            if fire.junction_id not in junctions:
                raise ValueError(
                    f"calendar fire flow refers to unknown junction {fire.junction_id!r}"
                )

    def multipliers(
        self, land_use: str, timebase: Timebase, calendar: DemandCalendar
    ) -> NDArray[np.float64]:
        """Deterministic common expectation factors; no events, fires or random draws."""
        return self._multipliers(land_use, self._axis(timebase, calendar))

    def _multipliers(self, land_use: str, axis: _LocalAxis) -> NDArray[np.float64]:
        normal = self.pattern(land_use)
        ramadan = self.pattern(land_use, ramadan=True)
        weekend = self._positive(f"demand_weekend_{land_use}")
        holiday = self._positive(f"demand_holiday_{land_use}")
        heatwave = self._positive(f"demand_heatwave_{land_use}")
        seasons = np.array(
            [self._positive(f"demand_season_m{m:02d}") for m in range(1, 13)]
        )
        iftar = self.parameter("iftar_hour_local", "h")
        if not 0 <= iftar < 24:
            raise ValueError("iftar_hour_local must be in [0, 24)")
        hour = np.where(axis.ramadan, (axis.hours - iftar) % 24, axis.hours)
        lower = np.floor(hour).astype(np.int64)
        fraction = hour - lower
        upper = (lower + 1) % 24
        low = np.where(axis.ramadan, ramadan[lower], normal[lower])
        high = np.where(axis.ramadan, ramadan[upper], normal[upper])
        result = low * (1 - fraction) + high * fraction
        result *= seasons[axis.months]
        result[axis.weekend] *= weekend
        result[axis.holidays] *= holiday
        result[axis.heatwave] *= heatwave
        if not np.all(np.isfinite(result)) or np.any(result <= 0):
            raise ValueError(
                f"{land_use}: demand multipliers must be finite and positive"
            )
        return result

    def _expectation(
        self, network: Network, calendar: DemandCalendar, axis: _LocalAxis
    ) -> NDArray[np.float64]:
        self._validate_calendar(network, calendar)
        land_uses = {zone.id: zone.land_use for zone in network.zones}
        profiles = {
            land: self._multipliers(land, axis)
            for land in sorted(set(land_uses.values()))
        }
        return np.column_stack(
            [
                profiles[land_uses[junction.zone]] * junction.base_demand
                for junction in network.junctions
            ]
        )

    def _ar1(
        self, seed: int, stream: str, n_ticks: int, kind: str
    ) -> NDArray[np.float64]:
        sigma = self.parameter(f"{kind}_sigma")
        phi = self.parameter(f"{kind}_phi")
        if sigma < 0:
            raise ValueError(f"{kind}_sigma must be non-negative")
        if not -1 < phi < 1:
            raise ValueError(f"{kind}_phi must be between -1 and 1")
        rng = SeedStreams(seed).stream(stream)
        standard = rng.standard_normal(n_ticks)
        errors = np.empty(n_ticks)
        errors[0] = sigma * standard[0]
        innovation_sigma = sigma * math.sqrt(1 - phi * phi)
        for i in range(1, n_ticks):
            errors[i] = phi * errors[i - 1] + innovation_sigma * standard[i]
        if not np.all(np.isfinite(errors)) or np.any(1 + errors <= 0):
            raise ValueError(
                f"{kind}: stochastic multipliers must be finite and positive"
            )
        return errors

    def _truth_noise(
        self, seed: int, zone_id: str, n_ticks: int
    ) -> NDArray[np.float64]:
        return self._ar1(seed, f"demand.noise.{zone_id}", n_ticks, "noise")

    def _forecast_error(
        self, seed: int, zone_id: str, n_ticks: int
    ) -> NDArray[np.float64]:
        return self._ar1(seed, f"demand.forecast.{zone_id}", n_ticks, "forecast")

    def truth(
        self, network: Network, timebase: Timebase, seed: int, calendar: DemandCalendar
    ) -> DemandSeries:
        axis = self._axis(timebase, calendar)
        values = self._expectation(network, calendar, axis)
        for zone in network.zones:
            columns = [
                i
                for i, junction in enumerate(network.junctions)
                if junction.zone == zone.id
            ]
            factor = 1 + self._truth_noise(seed, zone.id, timebase.n_ticks)
            for event in calendar.events:
                if event.zone_id == zone.id:
                    active = axis.active(event.start, event.end)
                    factor[active] *= event.multiplier
            values[:, columns] *= factor[:, None]
        for fire in calendar.fire_flows:
            column = next(
                i
                for i, junction in enumerate(network.junctions)
                if junction.id == fire.junction_id
            )
            active = axis.active(fire.start, fire.end)
            values[active, column] += fire.flow_m3s
        return self._series(network, timebase, values, EvidenceLabel.SIMULATION)

    def forecast(
        self, network: Network, timebase: Timebase, seed: int, calendar: DemandCalendar
    ) -> DemandSeries:
        values = self._expectation(network, calendar, self._axis(timebase, calendar))
        for zone in network.zones:
            columns = [
                i
                for i, junction in enumerate(network.junctions)
                if junction.zone == zone.id
            ]
            factor = 1 + self._forecast_error(seed, zone.id, timebase.n_ticks)
            values[:, columns] *= factor[:, None]
        return self._series(network, timebase, values, EvidenceLabel.MODEL)

    def _series(
        self,
        network: Network,
        timebase: Timebase,
        values: NDArray[np.float64],
        label: EvidenceLabel,
    ) -> DemandSeries:
        return DemandSeries(
            timebase,
            tuple(j.id for j in network.junctions),
            values,
            label,
            self.assumptions.content_hash(),
        )
