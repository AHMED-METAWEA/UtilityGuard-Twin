import { cleanup, render } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { Identifier } from "../Identifier";
import { expectEveryNumberLabelled } from "./labelled";
afterEach(cleanup);
it("passes labelled numbers and the narrow exemptions", () => {
  const { container } = render(<><span data-evidence-label="MODEL">12 m</span><time dateTime="2026-10-27">2026-10-27</time><span className="ug-badge" data-level="F1">F1</span><span hidden>123</span></>);
  expect(() => expectEveryNumberLabelled(container)).not.toThrow();
});
it("bites on an unlabelled visible number", () => {
  const { container } = render(<p>Pressure 42 m</p>);
  expect(() => expectEveryNumberLabelled(container)).toThrow(/42/);
});
it("rejects invalid labels and arbitrary exemption attributes", () => {
  const { container } = render(<span data-evidence-label="whatever" data-unlabelled-allowed>23</span>);
  expect(() => expectEveryNumberLabelled(container)).toThrow(/23/);
});

it("exempts Identifier digits but still rejects a bare number alongside it", () => {
  const { container, rerender } = render(<Identifier text="network_v12" />);
  expect(container.querySelector("code.ug-identifier[data-identifier]")?.textContent).toBe("network_v12");
  expect(() => expectEveryNumberLabelled(container)).not.toThrow();
  rerender(<><Identifier text="network_v12" /><span>42</span></>);
  expect(() => expectEveryNumberLabelled(container)).toThrow(/42/);
});
