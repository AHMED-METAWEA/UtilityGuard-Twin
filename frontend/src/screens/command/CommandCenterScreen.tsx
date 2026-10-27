import type { ScreenProps } from "../types";

// Placeholder registered by the lead (docs/DEMO_PLAN.md card D-00). The lane that owns
// `src/screens/command/` replaces it; its strings go in `src/screens/command/strings.ts`.
export function CommandCenterScreen({ route }: ScreenProps) {
  return (
    <>
      <h1>{route.title}</h1>
      <p>{route.empty}</p>
    </>
  );
}
