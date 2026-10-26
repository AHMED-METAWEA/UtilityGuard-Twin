"""Synthetic water demand, explicitly configured from a strict assumption set."""

from ug_water.demand.calendar import DemandCalendar, FireFlow, SpecialEvent
from ug_water.demand.model import DemandModel, DemandSeries

__all__ = ["DemandCalendar", "DemandModel", "DemandSeries", "FireFlow", "SpecialEvent"]
