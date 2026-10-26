import { Component } from "react";
import type { ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback: ReactNode;
  /** When this changes (a new state object), a failed part is tried again. */
  resetKey?: unknown;
}

interface State {
  failed: boolean;
  key: unknown;
}

/**
 * Isolates a part of the shell. If it throws while rendering, the fallback is shown and the rest
 * of the page, the honesty notice above all, stays on screen. The fallbacks claim nothing.
 */
export class Boundary extends Component<Props, State> {
  override state: State = { failed: false, key: this.props.resetKey };

  static getDerivedStateFromError(): Partial<State> {
    return { failed: true };
  }

  // A failure is tied to the input that caused it: new input gets a new try (review round 1).
  static getDerivedStateFromProps(props: Props, state: State): Partial<State> | null {
    return props.resetKey === state.key ? null : { failed: false, key: props.resetKey };
  }

  override render(): ReactNode {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}
