import { STRINGS } from "./strings";

export interface RouteDef {
  path: string;
  title: string;
  empty: string;
}

// Every screen of the demo plan (docs/DEMO_PLAN.md section 3), registered once by the lead so the
// Codex lanes never edit this file; each screen lives in `src/screens/<folder>/`.
export const ROUTES: readonly RouteDef[] = [
  {
    path: "/",
    title: STRINGS.pages.commandCenter.title,
    empty: STRINGS.pages.commandCenter.empty,
  },
  {
    path: "/map",
    title: STRINGS.pages.networkMap.title,
    empty: STRINGS.pages.networkMap.empty,
  },
  {
    path: "/sensors",
    title: STRINGS.pages.sensors.title,
    empty: STRINGS.pages.sensors.empty,
  },
  {
    path: "/scenarios",
    title: STRINGS.pages.scenarioLab.title,
    empty: STRINGS.pages.scenarioLab.empty,
  },
  {
    path: "/forecast",
    title: STRINGS.pages.forecast.title,
    empty: STRINGS.pages.forecast.empty,
  },
  {
    path: "/decision",
    title: STRINGS.pages.decision.title,
    empty: STRINGS.pages.decision.empty,
  },
  {
    path: "/runs",
    title: STRINGS.pages.runs.title,
    empty: STRINGS.pages.runs.empty,
  },
  {
    path: "/health",
    title: STRINGS.pages.systemHealth.title,
    empty: STRINGS.pages.systemHealth.empty,
  },
];

/** Hash routes (`#/health`): no server rewriting, works from a static folder, offline. */
export function pathFromHash(hash: string): string {
  const path = hash.startsWith("#") ? hash.slice(1) : hash;
  return path === "" ? "/" : path;
}

export function findRoute(path: string): RouteDef | null {
  return ROUTES.find((route) => route.path === path) ?? null;
}
