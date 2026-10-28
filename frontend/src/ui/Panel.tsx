import { useId } from "react";
import type { ReactNode } from "react";
export function Panel({ title, children }: { title: string; children: ReactNode }) {
  const id = useId();
  return <section className="ug-panel" aria-labelledby={id}><h2 id={id}>{title}</h2><div className="ug-panel-body">{children}</div></section>;
}
