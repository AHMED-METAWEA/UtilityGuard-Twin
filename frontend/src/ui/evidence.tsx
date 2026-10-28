import { createContext, useContext, useRef, useState, useLayoutEffect } from "react";
import type { ReactNode } from "react";
import type { EvidenceRecord } from "../generated/evidence-record";
import { EvidenceDrawer } from "./EvidenceDrawer";
export type EvidenceTarget = { evidence: EvidenceRecord; evidenceId?: never } | { evidenceId: string; evidence?: never };
type Selection = { id: string; record?: EvidenceRecord };
const Context = createContext<{ open: (target: EvidenceTarget, trigger: HTMLElement) => void } | null>(null);
export function useEvidence() {
  const context = useContext(Context);
  if (!context) throw new Error("Metric requires EvidenceProvider");
  return context;
}
/** Records are supplied locally; opening an id never initiates a request. */
export function EvidenceProvider({ children, records = [] }: { children: ReactNode; records?: readonly EvidenceRecord[] }) {
  const [selection, select] = useState<Selection | null>(null);
  const [drawerTop, setDrawerTop] = useState(0);
  const trigger = useRef<HTMLElement | null>(null);
  const openedRecords = useRef(new Map<string, EvidenceRecord>());
  const content = useRef<HTMLDivElement>(null);
  const active = selection !== null;
  useLayoutEffect(() => {
    if (!active) { content.current?.removeAttribute("inert"); return; }
    content.current?.setAttribute("inert", "");
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    // The modal starts below the shell notices, keeping the honesty indicators visible.
    const measure = () => setDrawerTop(Math.max(0, content.current?.querySelector(".ug-body")?.getBoundingClientRect().top ?? 0));
    measure();
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(measure);
    if (content.current) observer?.observe(content.current);
    window.addEventListener("resize", measure);
    return () => {
      observer?.disconnect();
      window.removeEventListener("resize", measure);
      document.body.style.overflow = previousOverflow;
    };
  }, [active]);
  const close = () => { content.current?.removeAttribute("inert"); select(null); trigger.current?.focus(); };
  return <Context.Provider value={{ open: (target, element) => {
    if (!selection) trigger.current = element;
    if (target.evidence) openedRecords.current.set(target.evidence.evidence_id, target.evidence);
    const record = target.evidence ?? records.find((item) => item.evidence_id === target.evidenceId) ?? openedRecords.current.get(target.evidenceId!);
    select({ id: target.evidence?.evidence_id ?? target.evidenceId!, record });
  } }}>
    <div ref={content}>{children}</div>
    {selection && <EvidenceDrawer top={drawerTop} evidenceId={selection.id} record={selection.record} onClose={close} />}
  </Context.Provider>;
}
