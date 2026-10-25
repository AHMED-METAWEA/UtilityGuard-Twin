import { fidelityBadge } from "../app/fidelity";
import type { LoadedNetwork } from "../app/fidelity";
import { STRINGS } from "../app/strings";

export function FidelityBadge({ network }: { network: LoadedNetwork | null }) {
  const view = fidelityBadge(network);
  return (
    <span
      className="ug-badge"
      data-level={view.level}
      data-downgraded={view.downgraded ? "true" : "false"}
      title={view.downgraded ? STRINGS.fidelity.downgraded : undefined}
      aria-label={`${STRINGS.fidelity.label}: ${view.text}`}
    >
      {view.text}
    </span>
  );
}
