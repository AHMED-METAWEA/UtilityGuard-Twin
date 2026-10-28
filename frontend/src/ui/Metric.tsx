import type { EvidenceRecord } from "../generated/evidence-record";
import { assertEvidenceLabel, EvidenceChip } from "./EvidenceChip";
import type { EvidenceLabel } from "./EvidenceChip";
import { useEvidence } from "./evidence";
import type { EvidenceTarget } from "./evidence";
import { formatValue } from "./format";
import { UI_STRINGS } from "./strings";
export type MetricProps = EvidenceTarget & {
  value: EvidenceRecord["value"]; unit: string | null; label: EvidenceLabel;
  range?: Pick<NonNullable<EvidenceRecord["uncertainty"]>, "p10" | "p50" | "p90">;
};
export function Metric(props: MetricProps) {
  assertEvidenceLabel(props.label);
  const { open } = useEvidence();
  if (props.evidence && (props.evidence.label !== props.label || props.evidence.value !== props.value || props.evidence.unit !== props.unit)) {
    throw new Error("Metric must match its evidence record");
  }
  if (!props.evidence && !props.evidenceId) throw new Error("Metric requires evidence or an evidence id");
  return <button type="button" className="ug-metric" data-evidence-label={props.label}
    aria-haspopup="dialog" onClick={(event) => open(props, event.currentTarget)}>
    <span className="ug-metric-value">{formatValue(props.value)}</span>
    {props.unit && <span className="ug-metric-unit">{props.unit}</span>}
    <EvidenceChip label={props.label} />
    {props.range && <span className="ug-metric-range">{["p10", "p50", "p90"].map((key) => {
      const quantile = key as "p10" | "p50" | "p90";
      return <span key={key}>{UI_STRINGS[quantile]}{": "}{formatValue(props.range![quantile])}{" "}</span>;
    })}</span>}
  </button>;
}
