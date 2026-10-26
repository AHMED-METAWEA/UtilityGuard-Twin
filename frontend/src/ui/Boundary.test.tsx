import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Boundary } from "./Boundary";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function Part({ fail }: { fail: boolean }) {
  if (fail) throw new Error("part exploded");
  return <span>part</span>;
}

describe("a boundary recovers on new input (review round 1 of T-B1-005)", () => {
  it("keeps the fallback while the input is the same and retries when it changes", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    const first = {};
    const { rerender } = render(
      <Boundary fallback={<span>fallback</span>} resetKey={first}>
        <Part fail />
      </Boundary>,
    );
    expect(screen.getByText("fallback")).toBeTruthy();
    rerender(
      <Boundary fallback={<span>fallback</span>} resetKey={first}>
        <Part fail={false} />
      </Boundary>,
    );
    expect(screen.getByText("fallback")).toBeTruthy(); // same input: no retry
    rerender(
      <Boundary fallback={<span>fallback</span>} resetKey={{}}>
        <Part fail={false} />
      </Boundary>,
    );
    expect(screen.getByText("part")).toBeTruthy(); // new input: tried again
  });
});
