import { Component } from "react";
import type { ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback: ReactNode;
}

/**
 * Isolates a part of the shell. If it throws while rendering, the fallback is shown and the rest
 * of the page, the honesty notice above all, stays on screen. The fallbacks claim nothing.
 */
export class Boundary extends Component<Props, { failed: boolean }> {
  override state = { failed: false };

  static getDerivedStateFromError(): { failed: boolean } {
    return { failed: true };
  }

  override render(): ReactNode {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}
