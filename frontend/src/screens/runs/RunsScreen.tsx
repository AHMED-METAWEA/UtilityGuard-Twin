import type { ScreenProps } from "../types";

// Placeholder registered by the lead (docs/DEMO_PLAN.md card D-00). The lane that owns
// `src/screens/runs/` replaces it; its strings go in `src/screens/runs/strings.ts`.
export function RunsScreen({ route }: ScreenProps) {
  return (
    <>
      <h1>{route.title}</h1>
      <p>{route.empty}</p>
    </>
  );
}
