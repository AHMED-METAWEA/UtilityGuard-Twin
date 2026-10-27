import ts from "typescript";
import { describe, expect, it } from "vitest";

import { STRINGS } from "./strings";

// All user-visible text lives in strings.ts so the Arabic translation can be added later
// (AGENTS.md, Language). This reads the sources of the shell and fails on text written inline.
const SOURCES = import.meta.glob<string>(["/src/app/**/*.tsx", "/src/ui/**/*.tsx", "/src/screens/**/*.tsx", "/src/main.tsx", "!/src/**/*.test.tsx"], {
  query: "?raw",
  import: "default",
  eager: true,
});

const TEXT_ATTRIBUTES = new Set(["title", "alt", "placeholder", "aria-label", "aria-description", "label"]);

/** Inline text found in a TSX source: JSX text, and string literals in text-bearing attributes. */
export function inlineText(source: string): string[] {
  const file = ts.createSourceFile("x.tsx", source, ts.ScriptTarget.ES2022, true, ts.ScriptKind.TSX);
  const found: string[] = [];
  const visit = (node: ts.Node): void => {
    if (ts.isJsxText(node) && node.text.trim() !== "") found.push(node.text.trim());
    if (ts.isJsxAttribute(node) && TEXT_ATTRIBUTES.has(node.name.getText(file))) {
      const init = node.initializer;
      if (init && ts.isStringLiteral(init) && init.text.trim() !== "") found.push(init.text);
      if (init && ts.isJsxExpression(init) && init.expression) {
        const e = init.expression;
        if (ts.isStringLiteral(e) || ts.isNoSubstitutionTemplateLiteral(e)) found.push(e.text);
        if (ts.isTemplateExpression(e)) {
          const heads = [e.head.text, ...e.templateSpans.map((s) => s.literal.text)];
          for (const text of heads) if (text.replace(/[\s:,.-]/g, "") !== "") found.push(text);
        }
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(file);
  return found;
}

describe("UI strings", () => {
  it("reads the shell sources", () => {
    expect(Object.keys(SOURCES).length).toBeGreaterThanOrEqual(5);
  });

  it("has no text written inline in a component", () => {
    const offenders = Object.entries(SOURCES).flatMap(([path, source]) =>
      inlineText(source).map((text) => `${path}: ${JSON.stringify(text)}`),
    );
    expect(offenders).toEqual([]);
  });

  it("finds inline text when it is there (the check bites)", () => {
    expect(inlineText("export const A = () => <p>Hello</p>;")).toEqual(["Hello"]);
    expect(inlineText('export const A = () => <a title="Open">x{y}</a>;')).toContain("Open");
    expect(inlineText('export const A = () => <a aria-label={`Fidelity: ${y}`}>{y}</a>;')).toContain("Fidelity: ");
    expect(inlineText("export const A = () => <p>{STRINGS.a.b}</p>;")).toEqual([]);
  });

  it("keeps every string non-empty, English-only and free of URLs", () => {
    const all: string[] = [];
    const walk = (node: unknown): void => {
      if (typeof node === "string") all.push(node);
      else if (typeof node === "object" && node !== null) Object.values(node).forEach(walk);
    };
    walk(STRINGS);
    expect(all.length).toBeGreaterThan(15);
    for (const text of all) {
      expect(text.trim()).not.toBe("");
      expect(text).not.toMatch(/[؀-ۿ]/); // Arabic arrives as a translation table later
      expect(text).not.toMatch(/https?:\/\//);
    }
  });

  it("states the fidelity wording of the Master Spec", () => {
    expect(STRINGS.fidelity.f1).toBe(
      "Fidelity F1: Real OSM streets, hand-drawn districts, inferred pipes, synthetic hydraulics",
    );
    expect(STRINGS.fidelity.none).toBe("No network loaded");
  });
});
