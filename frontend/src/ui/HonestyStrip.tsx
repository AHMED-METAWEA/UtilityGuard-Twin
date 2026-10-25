import { useState } from "react";

import { STRINGS } from "../app/strings";

/** The honesty notice. It can collapse to a chip but never disappears (Master Spec 13.3). */
export function HonestyStrip() {
  const [collapsed, setCollapsed] = useState(false);
  return (
    <section className="ug-honesty" aria-label={STRINGS.honesty.regionLabel} data-collapsed={collapsed}>
      {collapsed ? (
        <p className="ug-chip">{STRINGS.honesty.chip}</p>
      ) : (
        <p className="ug-strip">{STRINGS.honesty.statement}</p>
      )}
      <button type="button" onClick={() => setCollapsed(!collapsed)}>
        {collapsed ? STRINGS.honesty.expand : STRINGS.honesty.collapse}
      </button>
    </section>
  );
}
