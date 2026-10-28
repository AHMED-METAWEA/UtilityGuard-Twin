import type { EvidenceRecord } from "../generated/evidence-record";
import { UI_STRINGS } from "./strings";
export type EvidenceLabel = EvidenceRecord["label"];
export function assertEvidenceLabel(label: EvidenceLabel): void {
  if (!Object.prototype.hasOwnProperty.call(UI_STRINGS.labels, label)) throw new Error("A valid evidence label is required");
}
export function EvidenceChip({ label }: { label: EvidenceLabel }) {
  assertEvidenceLabel(label);
  return <span className="ug-evidence-chip" data-label={label}>{UI_STRINGS.labels[label]}</span>;
}
