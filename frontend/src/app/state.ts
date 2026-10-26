import type { LoadedNetwork } from "./fidelity";

export type ShellStatus =
  | { kind: "ready" }
  | { kind: "loading" }
  | { kind: "error"; message: string };

/** What the shell needs to draw itself. Everything but the status is optional input. */
export interface ShellState {
  status: ShellStatus;
  network: LoadedNetwork | null;
  /** The latest stream envelope, exactly as received; null before any. Never trusted unchecked. */
  lastEnvelope: unknown;
}

export const INITIAL_STATE: ShellState = {
  status: { kind: "ready" },
  network: null,
  lastEnvelope: null,
};
