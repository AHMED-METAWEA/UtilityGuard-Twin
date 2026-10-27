import type { RouteDef } from "../app/routes";

/** What the shell hands every screen; a screen draws only inside the main area. */
export interface ScreenProps {
  route: RouteDef;
}
