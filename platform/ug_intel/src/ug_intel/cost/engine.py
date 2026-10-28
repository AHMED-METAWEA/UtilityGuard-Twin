"""D-06 cost_v1: model-estimated, conditional on assumptions; advisory only.

A hypothesis run is SIMULATION conditional on the MODEL hypothesis. Physical
rates carry SIMULATION or MODEL evidence, never money or hidden fault tags.

Formulas per option o and sample s (template ids in parentheses):
- fix_now and wait: exposure_h = delay_h + crew_response_hours_s + repair_duration_hours_s.
  Quantities: lost_m3 = lost_water_m3_per_h x exposure_h;
  unserved_m3 = unserved_m3_per_h x exposure_h;
  extra_kwh = extra_energy_kwh_per_h x exposure_h. (cost.exposure.v1)
- isolate_then_fix: before isolation t_iso = crew_response_hours_s:
  lost_m3 = lost_rate x t_iso,
  unserved_m3 = unserved_rate x t_iso + unserved_isolated_rate x repair_duration_hours_s,
  extra_kwh = energy_rate x t_iso. (cost.isolation.v1)
- cost.lost_water.v1 = lost_m3 x water_production_cost;
  cost.unserved.v1 = unserved_m3 x unserved_water_penalty;
  cost.energy.v1 = extra_kwh x electricity_price;
  cost.repair.v1 = 1 repair x (repair_cost_emergency or repair_cost_planned);
  cost.crew.v1 = 1 visit x inspection_cost. total_s = sum of lines. (cost.total.v1)
- expected = mean; p10, p50, p90 with numpy.percentile(method="linear").
  (cost.total.v1)
- worst case = p90: "worst case" means the 90th percentile of the sampled costs,
  not a maximum and not a probability. (cost.worst_case.v1)
- regret_s(o) = total_s(o) - min over options of total_s;
  expected_regret(o) = mean over s. (cost.expected_regret.v1)
- net_benefit.v1 = expected(w) - expected(fix_now); it may be negative.
- E[total(o)] = q x E[X_o x p_w] + E[F_o], where q is the lost-water
  rate (m3/h), X_o the exposure hours, p_w the water price and F_o the sum
  of all other lines;
  q* = (E[F_wait] - E[F_fix]) / (E[X_fix x p_w] - E[X_wait x p_w]).
  All expectations use the same samples. If the denominator is 0 or q* < 0:
  INSUFFICIENT_EVIDENCE, "no break-even within non-negative leak rates".
  (break_even.lost_water_rate.v1)

One named RNG supplies sorted assumption draws, shared by every option. Collapsed
ranges use constant arrays: NumPy triangular rejects left == right. Sample means,
medians and percentiles may all change with the seed. Money lines contain exactly
one quantity times one assumed price; aggregate statistics reference those lines.
Count units encode the single repair and visit. Duration inputs show modes, physical
quantity inputs show sampled p50, and prices show modes; their product need not be
the mean of sampled costs. No independence approximation or product of summaries
is used to compute a cost.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray
from ug_core import grammar
from ug_core.assumptions import AssumptionSet
from ug_core.evidence import Evidenced, EvidenceLabel
from ug_core.numeric import finite
from ug_core.rng import SeedStreams

Samples = NDArray[np.float64]
Payload = dict[str, Any]
_ASSUMPTION_UNITS = {
    "water_production_cost": "EGP/m3",
    "unserved_water_penalty": "EGP/m3",
    "electricity_price": "EGP/kWh",
    "repair_cost_emergency": "EGP",
    "repair_cost_planned": "EGP",
    "inspection_cost": "EGP",
    "crew_response_hours": "h",
    "repair_duration_hours": "h",
}
_LINE_SPECS = (
    ("lost_water", "lost_water_m3", "m3", "water_production_cost"),
    ("unserved", "unserved_m3", "m3", "unserved_water_penalty"),
    ("energy", "extra_kwh", "kWh", "electricity_price"),
    ("repair", "repair_count", "count", "repair_cost_"),
    ("crew", "visit_count", "count", "inspection_cost"),
)


def _nonnegative(value: object, name: str) -> float:
    result = finite(value, name)
    if result < 0:
        raise ValueError(f"{name} must be non-negative")
    return result


@dataclass(frozen=True)
class Rate:
    """A physical rate; a hypothesis run is SIMULATION conditional on a MODEL hypothesis."""

    value: float
    unit: str
    label: EvidenceLabel | str
    ref: str

    def __post_init__(self) -> None:
        label = EvidenceLabel(self.label)
        if label not in {EvidenceLabel.SIMULATION, EvidenceLabel.MODEL}:
            raise ValueError("a rate must be SIMULATION or MODEL")
        if self.unit not in {"m3/h", "kWh/h"}:
            raise ValueError("a rate must have physical unit m3/h or kWh/h")
        grammar.require_identifier(self.ref, "rate evidence ref")
        object.__setattr__(self, "value", _nonnegative(self.value, "rate"))
        object.__setattr__(self, "label", label)


@dataclass(frozen=True)
class ExposureRates:
    lost_water_m3_per_h: Rate
    unserved_m3_per_h: Rate
    extra_energy_kwh_per_h: Rate
    unserved_isolated_m3_per_h: Rate | None = None

    def __post_init__(self) -> None:
        for name, unit in (
            ("lost_water_m3_per_h", "m3/h"),
            ("unserved_m3_per_h", "m3/h"),
            ("extra_energy_kwh_per_h", "kWh/h"),
            ("unserved_isolated_m3_per_h", "m3/h"),
        ):
            rate = getattr(self, name)
            if rate is None and name == "unserved_isolated_m3_per_h":
                continue
            if not isinstance(rate, Rate) or rate.unit != unit:
                raise ValueError(f"{name} must be a Rate in {unit}")


@dataclass(frozen=True)
class Option:
    option_id: str
    action: str
    delay_hours: float
    repair: str

    def __post_init__(self) -> None:
        grammar.require_identifier(self.option_id, "option_id")
        if self.action not in {"fix_now", "wait", "isolate_then_fix"}:
            raise ValueError("unknown cost option action")
        if self.repair not in {"emergency", "planned"}:
            raise ValueError("repair must be emergency or planned")
        delay = _nonnegative(self.delay_hours, "delay_hours")
        if self.action != "wait" and delay != 0:
            raise ValueError("fix_now and isolate_then_fix require delay_hours=0")
        object.__setattr__(self, "delay_hours", delay)


DEFAULT_OPTIONS = (
    Option("fix_now", "fix_now", 0, "emergency"),
    Option("wait_6h", "wait", 6, "emergency"),
    Option("wait_24h", "wait", 24, "planned"),
    Option("wait_72h", "wait", 72, "planned"),
)


def evidence_input(
    name: str,
    value: float,
    unit: str,
    label: EvidenceLabel | str,
    ref: str,
    *,
    formula: str | None = None,
    inputs: tuple[str, ...] = (),
) -> Payload:
    """Validate each input with the evidence kernel, including its money guard."""
    grammar.require_identifier(name, "input name")
    checked = Evidenced(
        value, EvidenceLabel(label), ref, unit=unit, formula=formula, inputs=inputs
    )
    return dict(
        name=name, value=checked.value, unit=unit, label=checked.label.value, ref=ref
    )


def _provenance(value: Mapping[str, Any], seed: int, assumption_set: str) -> Payload:
    required = {
        "run_id",
        "scenario_id",
        "seed",
        "network_version",
        "detector_version",
        "assumption_set",
        "cost_model",
    }
    if not required <= value.keys() or value.keys() - required - {"git_commit"}:
        raise ValueError(
            "provenance needs exactly the cost run fields and optional git_commit"
        )
    for name in required - {"seed"}:
        grammar.require_identifier(value[name], f"provenance.{name}")
    if (
        isinstance(value["seed"], bool)
        or not isinstance(value["seed"], int)
        or value["seed"] != seed
    ):
        raise ValueError("provenance seed must match the sampling seed")
    if value["assumption_set"] != assumption_set or value["cost_model"] != "cost_v1":
        raise ValueError(
            "provenance assumption_set and cost_model must match the calculation"
        )
    version = value["detector_version"]
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,31}_v[0-9]+", version) or re.search(
        "truth|fault|hidden|prob|conf|percent|pct|ground|inject", version
    ):
        raise ValueError("invalid detector_version")
    if "git_commit" in value and not grammar.is_git_commit(value["git_commit"]):
        raise ValueError("invalid git_commit")
    return dict(value)


class CostEngine:
    """A single paired sample set; every returned payload or array is a fresh copy."""

    def __init__(
        self,
        rates: ExposureRates,
        assumptions: AssumptionSet,
        *,
        seed: int,
        provenance: Mapping[str, Any],
        decision_id: str,
        n_samples: int = 1000,
        options: Sequence[Option] | None = None,
    ) -> None:
        rng = SeedStreams(seed).stream("cost.samples")
        if (
            isinstance(n_samples, bool)
            or not isinstance(n_samples, int)
            or n_samples < 1
        ):
            raise ValueError("n_samples must be a positive int")
        if not isinstance(rates, ExposureRates) or not isinstance(
            assumptions, AssumptionSet
        ):
            raise TypeError(
                "rates and assumptions must be ExposureRates and AssumptionSet"
            )
        grammar.require_identifier(decision_id, "decision_id")
        self.rates, self.assumptions = rates, assumptions
        self.decision_id, self.n_samples = decision_id, n_samples
        self._provenance = _provenance(provenance, seed, assumptions.set_id)
        selected = tuple(DEFAULT_OPTIONS if options is None else options)
        if options is None and rates.unserved_isolated_m3_per_h is not None:
            selected += (
                Option("isolate_then_fix", "isolate_then_fix", 0, "emergency"),
            )
        if len(selected) < 2 or any(not isinstance(o, Option) for o in selected):
            raise ValueError("at least two Option objects are required")
        if len({o.option_id for o in selected}) != len(selected):
            raise ValueError("option ids must be unique")
        if (
            any(o.action == "isolate_then_fix" for o in selected)
            and rates.unserved_isolated_m3_per_h is None
        ):
            raise ValueError("isolation requires an unserved_isolated_m3_per_h rate")
        self.options = selected
        self._draws: dict[str, Samples] = {}
        for name in sorted(_ASSUMPTION_UNITS):
            entry = assumptions.assumptions[name]
            if entry.unit != _ASSUMPTION_UNITS[name] or entry.distribution.min < 0:
                raise ValueError(
                    f"{name} must be non-negative with unit {_ASSUMPTION_UNITS[name]}"
                )
            d = entry.distribution
            self._draws[name] = (
                np.full(n_samples, d.mode, dtype=np.float64)
                if d.min == d.max
                else rng.triangular(d.min, d.mode, d.max, size=n_samples)
            )
        self._quantities: dict[str, tuple[Samples, ...]] = {}
        self._lines: dict[str, tuple[Samples, ...]] = {}
        self._totals: dict[str, Samples] = {}
        self._exposures: dict[str, Samples] = {}
        # Reject overflows instead of emitting apparently usable infinite money.
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            for option in selected:
                self._calculate(option)
            self._best = np.minimum.reduce(list(self._totals.values()))

    @property
    def assumption_samples(self) -> Mapping[str, Samples]:
        return {name: values.copy() for name, values in self._draws.items()}

    def _option(self, option: Option | str) -> Option:
        for candidate in self.options:
            if option == candidate or option == candidate.option_id:
                return candidate
        raise ValueError(f"unknown option: {option!r}")

    def evidence_id(self, option: Option | str, line: str) -> str:
        option = self._option(option)
        return grammar.require_identifier(
            f"ev_{self.decision_id}_{option.option_id}_{line}", "evidence_id"
        )

    def _calculate(self, option: Option) -> None:
        crew, repair = (
            self._draws["crew_response_hours"],
            self._draws["repair_duration_hours"],
        )
        exposure = (
            crew
            if option.action == "isolate_then_fix"
            else option.delay_hours + crew + repair
        )
        lost = self.rates.lost_water_m3_per_h.value * exposure
        unserved = self.rates.unserved_m3_per_h.value * exposure
        energy = self.rates.extra_energy_kwh_per_h.value * exposure
        if option.action == "isolate_then_fix":
            isolated = self.rates.unserved_isolated_m3_per_h
            assert isolated is not None
            unserved = unserved + isolated.value * repair
        quantities = (
            lost,
            unserved,
            energy,
            np.ones(self.n_samples),
            np.ones(self.n_samples),
        )
        prices = (
            "water_production_cost",
            "unserved_water_penalty",
            "electricity_price",
            f"repair_cost_{option.repair}",
            "inspection_cost",
        )
        lines = tuple(
            q * self._draws[p] for q, p in zip(quantities, prices, strict=True)
        )
        self._quantities[option.option_id], self._lines[option.option_id] = (
            quantities,
            lines,
        )
        self._totals[option.option_id] = np.sum(lines, axis=0)
        self._exposures[option.option_id] = exposure

    def total_samples(self, option: Option | str) -> Samples:
        return self._totals[self._option(option).option_id].copy()

    def regret_samples(self, option: Option | str) -> Samples:
        return self.total_samples(option) - self._best

    def _duration_inputs(self, option: Option, *, repair: bool = True) -> list[Payload]:
        names = ["crew_response_hours"] + (["repair_duration_hours"] if repair else [])
        result = [self._assumption_input(n) for n in names]
        if option.action == "wait":
            result.insert(
                0,
                evidence_input(
                    "delay_hours",
                    option.delay_hours,
                    "h",
                    "ASSUMPTION",
                    self.evidence_id(option, "delay_hours"),
                ),
            )
        return result

    def _assumption_input(self, name: str) -> Payload:
        entry = self.assumptions.assumptions[name]
        return evidence_input(
            name,
            entry.distribution.mode,
            entry.unit,
            "ASSUMPTION",
            self.assumptions.evidence_id(name),
        )

    def record(
        self,
        option: Option | str,
        line: str,
        value: float | None,
        *,
        unit: str,
        formula: str,
        inputs: list[Payload],
        template: str,
        samples: Samples | None = None,
        reason: str | None = None,
        label: str = "CALCULATED",
    ) -> Payload:
        """Build evidence through the shared kernel; a missing value needs a reason."""
        inputs = [
            evidence_input(
                item["name"],
                item["value"],
                item["unit"],
                item["label"],
                item["ref"],
                formula="value of referenced evidence record",
                inputs=(item["ref"],),
            )
            for item in inputs
        ]
        if value is None:
            if not reason:
                raise ValueError("missing evidence requires a reason")
            label = "INSUFFICIENT_EVIDENCE"
        checked = Evidenced(
            value,
            EvidenceLabel(label),
            self.evidence_id(option, line),
            unit=unit,
            formula=formula,
            inputs=tuple(i["ref"] for i in inputs),
        )
        result = dict(
            schema_version="1",
            evidence_id=checked.evidence_id,
            value=checked.value,
            unit=unit,
            label=checked.label.value,
            formula=formula,
            inputs=inputs,
            provenance=dict(self._provenance),
            explanation_template=template,
        )
        if unit == "EGP":
            result["kind"] = "cost"
        if samples is not None:
            if value is None:
                raise ValueError("INSUFFICIENT_EVIDENCE cannot carry uncertainty")
            p10, p50, p90 = np.percentile(samples, [10, 50, 90], method="linear")
            result["uncertainty"] = dict(
                p10=finite(p10),
                p50=finite(p50),
                p90=finite(p90),
                basis=f"{self.n_samples} seeded samples of the assumption ranges (assumption set {self.assumptions.set_id})",
            )
        if reason is not None:
            result["reason"] = reason
        return result

    def cost_lines(self, option: Option | str) -> list[Payload]:
        option = self._option(option)
        quantities, costs = (
            self._quantities[option.option_id],
            self._lines[option.option_id],
        )
        rates = (
            self.rates.lost_water_m3_per_h,
            self.rates.unserved_m3_per_h,
            self.rates.extra_energy_kwh_per_h,
        )
        result = []
        for index, (line, quantity, unit, price) in enumerate(_LINE_SPECS):
            if line == "repair":
                price += option.repair
            if index < 3:
                rate = rates[index]
                label, ref = rate.label, rate.ref
                if line == "unserved" and option.action == "isolate_then_fix":
                    # The composite quantity has two sources: expose both in its own record.
                    ref = self.evidence_id(option, "unserved_quantity")
                    isolated = self.rates.unserved_isolated_m3_per_h
                    assert isolated is not None
                    if isolated.label == "MODEL":
                        label = EvidenceLabel.MODEL
            else:
                label, ref = (
                    EvidenceLabel.ASSUMPTION,
                    self.evidence_id(option, quantity),
                )
            inputs = [
                evidence_input(
                    quantity,
                    float(np.percentile(quantities[index], 50, method="linear")),
                    unit,
                    label,
                    ref,
                ),
                self._assumption_input(price),
            ]
            if index < 3:
                inputs += self._duration_inputs(
                    option,
                    repair=option.action != "isolate_then_fix" or line == "unserved",
                )
            result.append(
                self.record(
                    option,
                    line,
                    float(costs[index].mean()),
                    unit="EGP",
                    formula=f"{quantity} * {price}",
                    inputs=inputs,
                    template=f"cost.{line}.v1",
                    samples=costs[index],
                )
            )
        return result

    def option_inputs(self, option: Option | str) -> list[Payload]:
        """Evidence for the explicit option delay and the single repair and visit."""
        option = self._option(option)
        result = []
        for name, value, unit in (
            ("delay_hours", option.delay_hours, "h"),
            ("repair_count", 1.0, "count"),
            ("visit_count", 1.0, "count"),
        ):
            result.append(
                self.record(
                    option,
                    name,
                    value,
                    unit=unit,
                    formula="option definition",
                    inputs=[],
                    template="cost.option.v1",
                    label="ASSUMPTION",
                )
            )
        if option.action == "isolate_then_fix":
            base, isolated = (
                self.rates.unserved_m3_per_h,
                self.rates.unserved_isolated_m3_per_h,
            )
            assert isolated is not None
            label = "MODEL" if "MODEL" in {base.label, isolated.label} else "SIMULATION"
            inputs = [
                evidence_input(
                    "unserved_m3_per_h", base.value, base.unit, base.label, base.ref
                ),
                evidence_input(
                    "unserved_isolated_m3_per_h",
                    isolated.value,
                    isolated.unit,
                    isolated.label,
                    isolated.ref,
                ),
                *self._duration_inputs(option),
            ]
            result.append(
                self.record(
                    option,
                    "unserved_quantity",
                    float(
                        np.percentile(
                            self._quantities[option.option_id][1], 50, method="linear"
                        )
                    ),
                    unit="m3",
                    formula="unserved_m3_per_h * crew_response_hours + unserved_isolated_m3_per_h * repair_duration_hours",
                    inputs=inputs,
                    template="cost.isolation.v1",
                    label=label,
                )
            )
        return result
