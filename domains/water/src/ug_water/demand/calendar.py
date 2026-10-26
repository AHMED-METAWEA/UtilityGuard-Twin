"""Explicit local calendar inputs. Windows are half-open [start, end).

Local datetimes are naive wall-clock values in the assumption set's fixed UTC
offset, never values from the machine's timezone database. All supplied calendar
effects are ASSUMPTION inputs, not observations of real events.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from ug_core.evidence import EvidenceLabel
from ug_core.grammar import require_identifier
from ug_core.numeric import finite


def _window(start: datetime, end: datetime) -> None:
    for value in (start, end):
        if not isinstance(value, datetime) or value.tzinfo is not None:
            raise ValueError("calendar windows need naive local datetimes")
    if end <= start:
        raise ValueError("calendar window end must be after start")


def _positive(value: float, name: str) -> float:
    result = finite(value, name)
    if result <= 0:
        raise ValueError(f"{name} must be positive")
    return result


@dataclass(frozen=True)
class SpecialEvent:
    zone_id: str
    start: datetime
    end: datetime
    multiplier: float

    label = EvidenceLabel.ASSUMPTION

    def __post_init__(self) -> None:
        require_identifier(self.zone_id, "event zone id")
        _window(self.start, self.end)
        object.__setattr__(
            self, "multiplier", _positive(self.multiplier, "event multiplier")
        )


@dataclass(frozen=True)
class FireFlow:
    junction_id: str
    start: datetime
    end: datetime
    flow_m3s: float

    label = EvidenceLabel.ASSUMPTION

    def __post_init__(self) -> None:
        require_identifier(self.junction_id, "fire-flow junction id")
        _window(self.start, self.end)
        object.__setattr__(self, "flow_m3s", _positive(self.flow_m3s, "fire flow m3/s"))


@dataclass(frozen=True)
class DemandCalendar:
    holidays: frozenset[date] = frozenset()
    ramadan: frozenset[date] = frozenset()
    heatwave: frozenset[date] = frozenset()
    events: tuple[SpecialEvent, ...] = ()
    fire_flows: tuple[FireFlow, ...] = ()

    def __post_init__(self) -> None:
        for name in ("holidays", "ramadan", "heatwave"):
            dates = frozenset(getattr(self, name))
            if any(type(value) is not date for value in dates):
                raise ValueError(f"{name} must contain local dates, not datetimes")
            object.__setattr__(self, name, dates)
        for name, kind in (("events", SpecialEvent), ("fire_flows", FireFlow)):
            items = tuple(getattr(self, name))
            if any(not isinstance(item, kind) for item in items):
                raise ValueError(f"{name} must contain {kind.__name__} instances")
            # Equal calendars produce equal floating-point accumulation order.
            items = tuple(
                sorted(items, key=lambda item: (item.start, item.end, repr(item)))
            )
            object.__setattr__(self, name, items)
