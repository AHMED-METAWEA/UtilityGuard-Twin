import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { DeckGLProps } from "../../../node_modules/@deck.gl/react/dist/deckgl.js";
import { NetworkMap, NetworkMapScreen } from "./NetworkMapScreen";
import { MAP_STRINGS as S } from "./strings";
import { createMapFixture, createTickFixture, MAP_CANDIDATES } from "../../fixtures/map";
import { ROUTES } from "../../app/routes";

const captured = vi.hoisted(() => ({ props: undefined as DeckGLProps | undefined }));
vi.mock("../../../node_modules/@deck.gl/react/dist/deckgl.js", () => ({ default: (props: DeckGLProps) => { captured.props = props; return <canvas />; } }));
beforeEach(() => {
  captured.props = undefined;
  vi.stubGlobal("ResizeObserver", class {
    constructor(private callback: ResizeObserverCallback) {}
    observe() { this.callback([{ contentRect: { width: 900, height: 580 } } as ResizeObserverEntry], this as unknown as ResizeObserver); }
    disconnect() {}
  });
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
function assertNumbers(root: HTMLElement) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let text: Node | null;
  while ((text = walker.nextNode())) if (/\d/.test(text.textContent ?? "") && !text.parentElement?.closest("[data-identifier], time")) expect(text.parentElement?.closest("[data-evidence-label]"), text.textContent ?? "").toBeTruthy();
}
function pick(id: string, element?: string) {
  // Inject the documented PickingInfo fields consumed by the component, without WebGL in jsdom.
  captured.props!.onHover!({ object: { id, element } } as never, {} as never);
}

describe("network map composition", () => {
  it("renders the fixture, layers, labelled candidate ranks and toggleable legends", () => {
    const { container } = render(<NetworkMapScreen route={ROUTES.find((r) => r.path === "/map")!} />);
    expect(container.querySelector("canvas")).toBeTruthy();
    expect(screen.getByText(S.fixture)).toBeTruthy();
    expect(screen.getByText(S.fidelity)).toBeTruthy();
    // The stream source belongs to the top-bar pill only (lead review).
    expect(screen.queryByText(/SIMULATED/)).toBeNull();
    expect(screen.getByRole("region", { name: S.candidates }).querySelectorAll("code")).toHaveLength(3);
    const legend = screen.getByRole("region", { name: S.legend });
    expect(legend.querySelectorAll("li")).toHaveLength(7);
    for (const [key, name] of Object.entries({ zones: S.zones, links: S.links, nodes: S.nodes, equipment: S.equipment, sensors: S.sensors, faults: S.faults, pressure: S.pressure, flow: S.flow })) {
      const toggle = screen.getByRole("checkbox", { name });
      const initial = (toggle as HTMLInputElement).checked;
      fireEvent.click(toggle);
      expect(legend.querySelector(`[data-layer-legend="${key}"]`) !== null).toBe(!initial);
      fireEvent.click(toggle);
    }
    assertNumbers(container);
  });
  it("labels sensor and model tooltip values separately from geometry attributes", () => {
    const { container } = render(<NetworkMapScreen route={ROUTES.find((r) => r.path === "/map")!} />);
    // fireEvent provides React's act wrapper for the Deck callback.
    const canvas = container.querySelector("canvas")!;
    canvas.addEventListener("click", () => pick("SENSOR_0", "J_0"));
    fireEvent.click(canvas);
    let tooltip = screen.getByRole("tooltip");
    expect(within(tooltip).getByText("SENSOR_0").hasAttribute("data-identifier")).toBe(true);
    expect(tooltip.querySelector('[data-evidence-label="SENSOR_SIM"]')?.textContent).toContain("m");
    expect(tooltip.querySelector('[data-evidence-label="ASSUMPTION"]')).toBeTruthy();
    canvas.addEventListener("pointermove", () => pick("L_40"));
    fireEvent.pointerMove(canvas);
    tooltip = screen.getByRole("tooltip");
    expect(tooltip.querySelector('[data-evidence-label="MODEL"]')?.textContent).toContain("L/s");
    expect(tooltip.querySelector('[data-evidence-label="CALCULATED"]')).toBeTruthy();
    expect(tooltip.textContent).toContain(S.score);
    assertNumbers(container);
  });
  it("includes public-geometry attribution and preserves the synthetic fixture fidelity", () => {
    const network = { ...createMapFixture(), fidelity: "F1" as const, geometry_label: "PUBLIC_GEOMETRY" as const };
    const { container } = render(<NetworkMap network={network} state={createTickFixture(network)} candidates={[]} />);
    expect(screen.getByText(S.f1)).toBeTruthy();
    expect(screen.getByText(S.attribution)).toBeTruthy();
    assertNumbers(container);
  });
  it("accepts the performance fixture without putting deck objects in the helpers", () => {
    const network = createMapFixture(800, 1100);
    render(<NetworkMap network={network} state={createTickFixture(network)} candidates={MAP_CANDIDATES} />);
    const layers = captured.props!.layers!.flat() as { id: string; props: { data: unknown[] } }[];
    expect(layers.find((l) => l.id === "nodes")!.props.data).toHaveLength(800);
    expect(layers.find((l) => l.id === "links")!.props.data).toHaveLength(1100);
  });
});
