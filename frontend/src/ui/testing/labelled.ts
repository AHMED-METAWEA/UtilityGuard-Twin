import { UI_STRINGS } from "../strings";

/** Walk actual text nodes, never attributes. Layout dimensions are not used (works in jsdom). */
export function expectEveryNumberLabelled(container: HTMLElement): void {
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
  const offenders: string[] = [];
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    if (!/\d/.test(node.textContent ?? "")) continue;
    const parent = node.parentElement;
    if (!parent) continue;
    let visible = true;
    for (let element: HTMLElement | null = parent; element; element = element.parentElement) {
      const style = getComputedStyle(element);
      if (element.hidden ||
        ["SCRIPT", "STYLE", "TEMPLATE"].includes(element.tagName) ||
        style.display === "none" || style.visibility === "hidden" || style.visibility === "collapse" || style.opacity === "0") visible = false;
    }
    if (!visible) continue;
    if (parent.closest('time, [data-identifier], section.ug-honesty[aria-label="Honesty notice"], .ug-badge[data-level]')) continue;
    const label = parent.closest("[data-evidence-label]")?.getAttribute("data-evidence-label");
    if (!label || !Object.prototype.hasOwnProperty.call(UI_STRINGS.labels, label)) offenders.push(node.textContent?.trim() ?? "");
  }
  if (offenders.length) throw new Error(`Visible numbers without evidence labels: ${offenders.join(" | ")}`);
}
