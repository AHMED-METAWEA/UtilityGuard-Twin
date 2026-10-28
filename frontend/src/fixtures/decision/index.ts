import type { EvidenceRecord, Input } from "../../generated/evidence-record";
import type { DecisionComparison, DecisionFixture } from "../../screens/decision/types";
import { DECISION_STRINGS as S } from "../../screens/decision/strings";
const provenance = { run_id: "fixture_decision", assumption_set: "fixture_prices_v1", cost_model: "fixture_cost_v1" };
function input(name: string, value: number, unit: string, label: Input["label"], ref: string): Input {
  return { name, value, unit, label, ref };
}
function record(id: string, value: number, unit: string, inputs: Input[], formula: string, cost = false): EvidenceRecord {
  return { schema_version: "1", evidence_id: id, kind: cost ? "cost" : "quantity", value, unit, label: "CALCULATED", inputs, formula, provenance };
}
/** Every comparison record is a physical quantity times one explicit assumption price.
 * Aggregate rates bundle the five line rates using their fixed physical ratios.
 * Regret rates normalize opportunity cost by that option's modeled volume.
 * These are display fixtures, not an implementation of the decision engine.
 */
export function createDecisionFixture(): DecisionFixture {
  const evidence: EvidenceRecord[] = [];
  const supportingEvidence: EvidenceRecord[] = [];
  function cost(id: string, quantity: number, unit: "m3" | "kWh", price: number, priceUnit: string, basis: string): EvidenceRecord {
    const inputs = [input("quantity", quantity, unit, "MODEL", `${id}:quantity`), input("unit_price", price, priceUnit, "ASSUMPTION", `${id}:price`)];
    const item = record(id, quantity * price, S.units.money, inputs, "quantity * unit_price", true);
    item.explanation_template = "fixture.cost.v1";
    item.reason = basis;
    item.uncertainty = { p10: Number(item.value) * 0.8, p50: Number(item.value), p90: Number(item.value) * 1.2, basis: S.priceBasis };
    evidence.push(item);
    for (const source of inputs) supportingEvidence.push({ schema_version: "1", evidence_id: source.ref, value: source.value, unit: source.unit,
      label: source.label, formula: null, inputs: [], provenance,
      explanation_template: "fixture.input.v1", reason: source.label === "ASSUMPTION" ? S.priceBasis : S.scope });
    return item;
  }
  // Each row: delay, modeled lost-water volume, expedited material/labor rates.
  const configs = [
    { id: "fix_now", delay: 0, volume: 10, repair: 400, crew: 300 },
    { id: "wait_short", delay: 6, volume: 20, repair: 100, crew: 100 },
    { id: "wait_day", delay: 24, volume: 50, repair: 100, crew: 100 },
    { id: "wait_extended", delay: 72, volume: 130, repair: 100, crew: 100 },
  ];
  const category = S.categories;
  const rows = configs.map(c => {
    const lines = [
      cost(`${c.id}:lost_water`, c.volume, "m3", 10, "EGP/m3", category.lost_water),
      cost(`${c.id}:unserved_demand`, c.volume / 2, "m3", 20, "EGP/m3", category.unserved_demand),
      cost(`${c.id}:energy`, c.volume * 2, "kWh", 2, "EGP/kWh", category.energy),
      cost(`${c.id}:repair`, c.volume / 10, "m3", c.repair, "EGP/m3", category.repair),
      cost(`${c.id}:crew`, c.volume / 10, "m3", c.crew, "EGP/m3", category.crew),
    ];
    const price = 10 + 0.5 * 20 + 2 * 2 + c.repair / 10 + c.crew / 10;
    const expected = cost(`${c.id}:expected`, c.volume, "m3", price, "EGP/m3", S.aggregate);
    // Exactly the same quantity with the upper price-range rate, not a real-event probability.
    const worst = cost(`${c.id}:worst`, c.volume, "m3", price * 1.2, "EGP/m3", S.priceBasis);
    return { c, lines, price, expected, worst };
  });
  const minimum = Math.min(...rows.map(r => Number(r.expected.value)));
  const options: DecisionComparison["options"] = rows.map(r => {
    const regret = cost(`${r.c.id}:regret`, r.c.volume, "m3", (Number(r.expected.value) - minimum) / r.c.volume, "EGP/m3", S.aggregate);
    return { option_id: r.c.id, action: r.c.delay ? "wait" : "fix_now", delay_hours: r.c.delay,
      expected_cost: r.expected.evidence_id, worst_case: r.worst.evidence_id, expected_regret: regret.evidence_id,
      cost_lines: r.lines.map(line => line.evidence_id) };
  });
  // Fixed hourly physical rates: lost water + unserved demand + extra pumping.
  const hourly = record("waiting:hourly", 40, S.units.hourly, [
    input("lost_water_rate", 5 / 3, "m3/h", "MODEL", "waiting:lost-rate"),
    input("unserved_rate", 5 / 6, "m3/h", "MODEL", "waiting:unserved-rate"),
    input("energy_rate", 10 / 3, "kWh/h", "MODEL", "waiting:energy-rate"),
    input("water_price", 10, "EGP/m3", "ASSUMPTION", "waiting:water-price"),
    input("unserved_price", 20, "EGP/m3", "ASSUMPTION", "waiting:unserved-price"),
    input("energy_price", 2, "EGP/kWh", "ASSUMPTION", "waiting:energy-price"),
  ], "lost_water_rate * water_price + unserved_rate * unserved_price + energy_rate * energy_price");
  hourly.uncertainty = { p10: 32, p50: 40, p90: 48, basis: S.priceBasis };
  const now = rows[0]!;
  const netBenefits = rows.slice(1).map(r => ({ option_id: r.c.id, evidence: record(`${r.c.id}:net`, Number(r.expected.value) - Number(now.expected.value), S.units.money, [
    input("wait_cost", Number(r.expected.value), "EGP", "CALCULATED", r.expected.evidence_id),
    input("acting_now_cost", Number(now.expected.value), "EGP", "CALCULATED", now.expected.evidence_id),
  ], "wait_cost - acting_now_cost", true) }));
  // Short wait: wait = base repair + duration * leak * bundled operating rate.
  // Fix = expedited repair + same baseline operating cost. q* = (700 - 400)/(6*24).
  const breakEven = record("break-even:short", 300 / 144, S.units.flow, [
    input("expedited_repair_premium", 300, "EGP", "CALCULATED", "break-even:premium"),
    input("delay", 6, "h", "ASSUMPTION", "wait_short:delay"),
    input("operating_rate_per_leak_volume", 24, "EGP/m3", "ASSUMPTION", "break-even:operating-price"),
  ], "expedited_repair_premium / (delay * operating_rate_per_leak_volume)");
  breakEven.explanation_template = "fixture.break_even.v1";
  breakEven.reason = "Hold each option’s repair excavation and crew volume fixed while varying leak flow. Operating cost includes lost water, unserved demand and energy at fixed ratios. Short wait only.";
  const comparison: DecisionComparison = { schema_version: "1", decision_id: "fixture_comparison", run_id: "fixture_decision", incident_id: "fixture_incident",
    assumption_set: "fixture_prices_v1", advisory: true, options, break_even: [{ between: ["fix_now", "wait_short"], parameter: "leak_flow", evidence_id: breakEven.evidence_id }],
    preferred_by_expected_cost: rows.find(r => Number(r.expected.value) === minimum)!.c.id, evidence };
  return { comparison, supportingEvidence, waitingCost: hourly, netBenefits, breakEven };
}
export const decisionFixture = createDecisionFixture();
