import type { ReactNode } from "react";
import type { EvidenceLabel } from "../../generated/common";

/** Temporary adapter until Lane A's Metric is available. */
export function Value({ children, label = "SENSOR_SIM" }: { children: ReactNode; label?: EvidenceLabel }) {
  return <span className="ug-sensor-value" data-evidence-label={label}>{children}</span>;
}
