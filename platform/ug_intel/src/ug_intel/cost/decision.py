"""Advisory option comparisons: model-estimated, conditional on assumptions.

expected_cost, worst_case and expected_regret are evidence ID strings resolving
in the top-level evidence list, as are cost_lines. No choice authorises an action.
The least expected sampled cost is a descriptive preference; exact ties give null.
Net benefits retain their sign. Regret is paired by sample, never computed by
subtracting the minimum of option means. Worst case means sampled p90, not a maximum.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
from ug_core import grammar
from ug_core.assumptions import AssumptionSet
from ug_core.numeric import finite

from ug_intel.cost.engine import (
    CostEngine,
    ExposureRates,
    Option,
    Payload,
    evidence_input,
)


def _reference(record: Payload, name: str) -> Payload:
    return evidence_input(
        name,
        record["value"],
        record["unit"],
        record["label"],
        record["evidence_id"],
        formula=record["formula"],
        inputs=tuple(i["ref"] for i in record["inputs"]),
    )


def compare(
    rates: ExposureRates,
    assumptions: AssumptionSet,
    *,
    seed: int,
    provenance: Mapping[str, Any],
    decision_id: str,
    incident_id: str,
    n_samples: int = 1000,
    options: Sequence[Option] | None = None,
) -> Payload:
    """Return D-01's comparison shape, with full evidence and no real-world odds.

    Net benefit records use each wait option's id and suffix net_benefit.
    Break-even uses fix_now's id and suffix break_even_lost_water_rate; it is
    emitted when the canonical fix_now and wait_24h options are present.
    """
    grammar.require_identifier(incident_id, "incident_id")
    engine = CostEngine(
        rates,
        assumptions,
        seed=seed,
        provenance=provenance,
        decision_id=decision_id,
        n_samples=n_samples,
        options=options,
    )
    evidence: list[Payload] = []
    line_records = {o.option_id: engine.cost_lines(o) for o in engine.options}
    totals: dict[str, Payload] = {}
    for option in engine.options:
        evidence.extend(engine.option_inputs(option))
        lines = line_records[option.option_id]
        evidence.extend(lines)
        samples = engine.total_samples(option)
        totals[option.option_id] = engine.record(
            option,
            "total",
            float(samples.mean()),
            unit="EGP",
            formula="mean(sum_s(cost.lost_water.v1, cost.unserved.v1, cost.energy.v1, cost.repair.v1, cost.crew.v1))",
            inputs=[_reference(line, f"line_{i}") for i, line in enumerate(lines)],
            template="cost.total.v1",
            samples=samples,
        )
        evidence.append(totals[option.option_id])
    total_inputs = [
        _reference(totals[o.option_id], f"total_{i}")
        for i, o in enumerate(engine.options)
    ]
    entries = []
    for option in engine.options:
        total = totals[option.option_id]
        worst = engine.record(
            option,
            "worst_case",
            total["uncertainty"]["p90"],
            unit="EGP",
            formula="percentile(total_s, 90, method='linear')",
            inputs=[_reference(total, "total")],
            template="cost.worst_case.v1",
        )
        regret = engine.record(
            option,
            "expected_regret",
            float(engine.regret_samples(option).mean()),
            unit="EGP",
            formula=f"mean(total_s({option.option_id}) - min_o(total_s(o)))",
            inputs=total_inputs,
            template="cost.expected_regret.v1",
            samples=engine.regret_samples(option),
        )
        evidence.extend([worst, regret])
        entries.append(
            dict(
                option_id=option.option_id,
                action=option.action,
                delay_hours=option.delay_hours,
                expected_cost=total["evidence_id"],
                worst_case=worst["evidence_id"],
                expected_regret=regret["evidence_id"],
                cost_lines=[r["evidence_id"] for r in line_records[option.option_id]],
            )
        )
    fixing = [o for o in engine.options if o.action == "fix_now"]
    if len(fixing) != 1:
        raise ValueError("a comparison requires exactly one fix_now option")
    fix = fixing[0]
    for wait in engine.options:
        if wait.action == "wait":
            evidence.append(
                engine.record(
                    wait,
                    "net_benefit",
                    totals[wait.option_id]["value"] - totals[fix.option_id]["value"],
                    unit="EGP",
                    formula="expected(wait) - expected(fix_now)",
                    inputs=[
                        _reference(totals[wait.option_id], "wait_total"),
                        _reference(totals[fix.option_id], "fix_now_total"),
                    ],
                    template="net_benefit.v1",
                )
            )
    break_even = []
    waiting = [
        o
        for o in engine.options
        if o.option_id == "wait_24h" and o.action == "wait" and o.delay_hours == 24
    ]
    if fix.option_id == "fix_now" and waiting:
        wait = waiting[0]
        # Subtracting lost cost from the total can cancel small non-water costs.
        # Sum the other four lines directly instead, using the same paired draws.
        fix_other = np.sum(engine._lines[fix.option_id][1:], axis=0)
        wait_other = np.sum(engine._lines[wait.option_id][1:], axis=0)
        price = engine._draws["water_production_cost"]
        denominator = finite(
            np.mean(engine._exposures[fix.option_id] * price)
            - np.mean(engine._exposures[wait.option_id] * price)
        )
        numerator = finite(wait_other.mean() - fix_other.mean())
        value = None if denominator == 0 else numerator / denominator
        reason = None
        if value is None or value < 0:
            value = None
            reason = "no break-even within non-negative leak rates"
        crossing = engine.record(
            fix,
            "break_even_lost_water_rate",
            value,
            unit="m3/h",
            formula="(E[F_wait] - E[F_fix]) / (E[X_fix * p_w] - E[X_wait * p_w])",
            inputs=[
                _reference(line, f"{side}_line_{i}")
                for side, selected in (("fix", fix), ("wait", wait))
                for i, line in enumerate(line_records[selected.option_id])
            ],
            template="break_even.lost_water_rate.v1",
            reason=reason,
        )
        evidence.append(crossing)
        break_even.append(
            dict(
                between=[fix.option_id, wait.option_id],
                parameter="lost_water_m3_per_h",
                evidence_id=crossing["evidence_id"],
            )
        )
    minimum = min(t["value"] for t in totals.values())
    winners = [
        o.option_id for o in engine.options if totals[o.option_id]["value"] == minimum
    ]
    # Prefixing identifiers with underscores is ambiguous if an option id contains
    # another suffix; reject such collisions rather than emit duplicate evidence.
    ids = [r["evidence_id"] for r in evidence]
    if len(ids) != len(set(ids)):
        raise ValueError("option ids cause colliding evidence ids")
    return dict(
        schema_version="1",
        decision_id=decision_id,
        run_id=provenance["run_id"],
        incident_id=incident_id,
        assumption_set=assumptions.set_id,
        advisory=True,
        options=entries,
        break_even=break_even,
        preferred_by_expected_cost=winners[0] if len(winners) == 1 else None,
        evidence=evidence,
    )
