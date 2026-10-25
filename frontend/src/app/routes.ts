import { STRINGS } from "./strings";

export interface RouteDef {
  path: string;
  title: string;
  empty: string;
}

export const ROUTES: readonly RouteDef[] = [
  {
    path: "/",
    title: STRINGS.pages.commandCenter.title,
    empty: STRINGS.pages.commandCenter.empty,
  },
  {
    path: "/scenarios",
    title: STRINGS.pages.scenarioLab.title,
    empty: STRINGS.pages.scenarioLab.empty,
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
