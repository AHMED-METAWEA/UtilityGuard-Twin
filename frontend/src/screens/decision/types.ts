import type { EvidenceRecord } from "../../generated/evidence-record";
/** Local D-01 draft; monetary fields and cost_lines refer to evidence ids. */
export interface DecisionComparison {
  schema_version: "1"; decision_id: string; run_id: string; incident_id: string;
  assumption_set: string; advisory: true;
  options: { option_id: string; action: "fix_now" | "wait" | "isolate_then_fix";
    delay_hours: number; expected_cost: string; worst_case: string; expected_regret: string; cost_lines: string[] }[];
  break_even: { between: [string, string]; parameter: string; evidence_id: string }[];
  preferred_by_expected_cost: string | null; evidence: EvidenceRecord[];
}
export interface DecisionFixture {
  comparison: DecisionComparison; supportingEvidence: EvidenceRecord[];
  waitingCost: EvidenceRecord;
  netBenefits: { option_id: string; evidence: EvidenceRecord }[];
  breakEven: EvidenceRecord;
}
