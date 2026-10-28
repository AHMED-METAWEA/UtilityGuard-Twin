import { useEffect, useId, useRef } from "react";
import type { EvidenceRecord } from "../generated/evidence-record";
import { EvidenceChip } from "./EvidenceChip";
import { Identifier } from "./Identifier";
import { Metric } from "./Metric";
import { UI_STRINGS as S } from "./strings";
export function EvidenceDrawer({ record, evidenceId, onClose, top = 0 }: { record?: EvidenceRecord; evidenceId: string; onClose: () => void; top?: number }) {
  const ref = useRef<HTMLElement>(null);
  const title = useId();
  useEffect(() => { ref.current?.querySelector<HTMLButtonElement>("button")?.focus(); }, [evidenceId]);
  return <div className="ug-drawer-backdrop" style={{ top }}>
    <aside ref={ref} className="ug-evidence-drawer" role="dialog" aria-modal="true" aria-labelledby={title}
      onKeyDown={(event) => {
        if (event.key === "Escape") { event.preventDefault(); onClose(); }
        if (event.key === "Tab") {
          const items = ref.current?.querySelectorAll<HTMLButtonElement>("button");
          if (!items?.length) return;
          const first = items[0], last = items[items.length - 1];
          if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
          else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
        }
      }}>
      <header><h2 id={title}>{S.evidence}</h2><button type="button" onClick={onClose}>{S.close}</button></header>
      {record ? <>
        <Metric evidence={record} value={record.value} unit={record.unit} label={record.label} range={record.uncertainty} />
        <h3>{S.formula}</h3><p>{record.formula ? <span data-evidence-label={record.label}>{record.formula}</span> : S.absent}</p>
        <h3>{S.inputs}</h3>
        <dl>{record.inputs.map((input, index) => <div key={index}>
          <dt><Identifier text={input.name} /></dt>
          <dd><Metric value={input.value} unit={input.unit} label={input.label} evidenceId={input.ref} /></dd>
          <dd><Identifier text={input.ref} /></dd>
        </div>)}</dl>
        <h3>{S.provenance}</h3>
        <Identifier text={evidenceId} />
        <dl>{Object.entries(record.provenance).map(([key, value]) => <div key={key}><dt><Identifier text={key} /></dt><dd>
          {value == null ? S.absent : <Identifier text={String(value)} />}
        </dd></div>)}</dl>
        <h3>{S.version}</h3><Identifier text={record.schema_version} />
        <h3>{S.uncertainty}</h3>{record.uncertainty ? <>
          <Metric value={record.value} unit={record.unit} label={record.label} evidence={record} range={record.uncertainty} />
          <p data-evidence-label={record.label}>{record.uncertainty.basis}</p>
        </> : <p>{S.absent}</p>}
        <h3>{S.explanation}</h3>{record.reason && <p data-evidence-label={record.label}>{record.reason}</p>}{record.explanation_template ?
          <p data-evidence-label={record.label}>{record.explanation_template}</p> : <p>{S.absent}</p>}
      </> : <><EvidenceChip label={S.labels.INSUFFICIENT_EVIDENCE} /><p>{S.unavailable}</p>
        <Identifier text={evidenceId} /></>}
    </aside>
  </div>;
}
