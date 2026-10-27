import type { ScreenProps } from "../types";

// Placeholder registered by the lead (docs/DEMO_PLAN.md card D-00). The lane that owns
// `src/screens/forecast/` replaces it; its strings go in `src/screens/forecast/strings.ts`.
export function ForecastScreen({ route }: ScreenProps) {
  return (
    <>
      <h1>{route.title}</h1>
      <p>{route.empty}</p>
    </>
  );
}
