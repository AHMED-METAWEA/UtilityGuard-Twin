import { useEffect, useState } from "react";

import { Boundary } from "../ui/Boundary";
import { FidelityBadge } from "../ui/FidelityBadge";
import { HonestyStrip } from "../ui/HonestyStrip";
import { StreamSourcePill } from "../ui/StreamSourcePill";
import { geometryNotice, readNetwork } from "./fidelity";
import type { LoadedNetwork, NetworkRead } from "./fidelity";
import { ROUTES, findRoute, pathFromHash } from "./routes";
import { INITIAL_STATE } from "./state";
import type { ShellState } from "./state";
import { STRINGS } from "./strings";

function useHashPath(): string {
  const [path, setPath] = useState(() => pathFromHash(window.location.hash));
  useEffect(() => {
    const onChange = () => setPath(pathFromHash(window.location.hash));
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return path;
}

// Fallbacks used when a part of the shell fails to render. They state nothing the data could
// contradict: the fidelity is "could not be determined" and the source is "unknown".
function BadgeFallback() {
  return (
    <span className="ug-badge" data-level="none" data-downgraded="true" aria-label={`${STRINGS.fidelity.label}: ${STRINGS.fidelity.unknown}`}>
      {STRINGS.fidelity.unknown}
    </span>
  );
}

function PillFallback() {
  return (
    <span className="ug-pill" data-source="unknown" aria-label={STRINGS.stream.label}>
      <span className="ug-pill-label">{STRINGS.stream.label}</span>
      <strong>{STRINGS.stream.unknown}</strong>
    </span>
  );
}

function ScreenFallback() {
  return (
    <div role="alert">
      <h1>{STRINGS.status.errorTitle}</h1>
      <p>{STRINGS.status.errorHint}</p>
    </div>
  );
}

function Screen({ state, path }: { state: ShellState; path: string }) {
  if (state.status.kind === "loading") {
    return <p role="status">{STRINGS.status.loading}</p>;
  }
  if (state.status.kind === "error") {
    return (
      <div role="alert">
        <h1>{STRINGS.status.errorTitle}</h1>
        <p>{state.status.message}</p>
        <p>{STRINGS.status.errorHint}</p>
      </div>
    );
  }
  const route = findRoute(path);
  if (route === null) {
    return (
      <>
        <h1>{STRINGS.pages.notFound.title}</h1>
        <p>{STRINGS.pages.notFound.body}</p>
      </>
    );
  }
  return (
    <>
      <h1>{route.title}</h1>
      <p>{route.empty}</p>
    </>
  );
}

/**
 * The shell: top bar with the Fidelity badge and the stream-source indicator, the honesty
 * notice, navigation and the screen. The first three are drawn in every state (ready, loading,
 * error, unknown address), because the screen only fills the main area.
 */
// The badge and the notice's F1 geometry line come from ONE read of the network (review round 1):
// a value that changed between two reads could otherwise show the F1 badge without the
// attribution. An accessor is never called; a network that cannot be read gives the fallback
// badge and the plain notice, which claim nothing.
function BadgeFromRead({ read }: { read: NetworkRead }) {
  return read.readable ? <FidelityBadge network={read.network as LoadedNetwork | null} /> : <BadgeFallback />;
}

function HonestyFromRead({ read }: { read: NetworkRead }) {
  const line = read.readable ? geometryNotice(read.network as LoadedNetwork | null) : null;
  return <HonestyStrip geometryNotice={line} />;
}

function PillFromState({ state }: { state: ShellState }) {
  return <StreamSourcePill envelope={state.lastEnvelope} />;
}

// Last resort when the whole shell fails to render: the notice in full and indicators that claim
// nothing. It reads no props and no state, so nothing the data holds can break it.
function StaticShell() {
  return (
    <div className="ug-shell">
      <header className="ug-topbar">
        <span className="ug-brand">{STRINGS.appName}</span>
        <BadgeFallback />
        <PillFallback />
      </header>
      <section className="ug-honesty" aria-label={STRINGS.honesty.regionLabel}>
        <p className="ug-strip">{STRINGS.honesty.statement}</p>
      </section>
      <main>
        <ScreenFallback />
      </main>
    </div>
  );
}

export function App(props: { state?: ShellState; path?: string }) {
  return (
    <Boundary fallback={<StaticShell />}>
      <Shell {...props} />
    </Boundary>
  );
}

function Shell({ state = INITIAL_STATE, path }: { state?: ShellState; path?: string }) {
  const hashPath = useHashPath();
  const current = path ?? hashPath;
  const read = readNetwork(state);
  return (
    <div className="ug-shell">
      <header className="ug-topbar">
        <span className="ug-brand">{STRINGS.appName}</span>
        <Boundary fallback={<BadgeFallback />} resetKey={state}>
          <BadgeFromRead read={read} />
        </Boundary>
        <Boundary fallback={<PillFallback />} resetKey={state}>
          <PillFromState state={state} />
        </Boundary>
      </header>
      <Boundary fallback={<HonestyStrip />} resetKey={state}>
        <HonestyFromRead read={read} />
      </Boundary>
      <div className="ug-body">
        <nav aria-label={STRINGS.nav.label}>
          <ul>
            {ROUTES.map((route) => (
              <li key={route.path}>
                <a href={`#${route.path}`} aria-current={route.path === current ? "page" : undefined}>
                  {route.title}
                </a>
              </li>
            ))}
          </ul>
        </nav>
        <main>
          <Boundary fallback={<ScreenFallback />} resetKey={state}>
            <Screen state={state} path={current} />
          </Boundary>
        </main>
      </div>
    </div>
  );
}
