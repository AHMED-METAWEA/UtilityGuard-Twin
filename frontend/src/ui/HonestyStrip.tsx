import { useState } from "react";

import { STRINGS } from "../app/strings";

/**
 * The honesty notice. It can collapse to a chip but never disappears (Master Spec 13.3). For an F1
 * network it adds the geometry line (OpenStreetMap attribution, hand-drawn districts), which stays
 * visible when the notice is collapsed.
 */
export function HonestyStrip({ geometryNotice = null }: { geometryNotice?: string | null }) {
  const [collapsed, setCollapsed] = useState(false);
  return (
    <section className="ug-honesty" aria-label={STRINGS.honesty.regionLabel} data-collapsed={collapsed}>
      {collapsed ? (
        <p className="ug-chip">{STRINGS.honesty.chip}</p>
      ) : (
        <p className="ug-strip">{STRINGS.honesty.statement}</p>
      )}
      {geometryNotice ? <p className="ug-geometry-notice">{geometryNotice}</p> : null}
      <button type="button" onClick={() => setCollapsed(!collapsed)}>
        {collapsed ? STRINGS.honesty.expand : STRINGS.honesty.collapse}
      </button>
    </section>
  );
}
