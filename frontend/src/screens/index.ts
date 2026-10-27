// The screen for each route path (docs/DEMO_PLAN.md card D-00). Written once by the lead; a lane
// changes only the component inside its own folder, never this map.
import type { ComponentType } from "react";

import { CommandCenterScreen } from "./command/CommandCenterScreen";
import { DecisionStudioScreen } from "./decision/DecisionStudioScreen";
import { ForecastScreen } from "./forecast/ForecastScreen";
import { NetworkMapScreen } from "./map/NetworkMapScreen";
import { RunsScreen } from "./runs/RunsScreen";
import { ScenarioLabScreen } from "./scenarios/ScenarioLabScreen";
import { SensorsScreen } from "./sensors/SensorsScreen";
import type { ScreenProps } from "./types";

export const SCREENS: Readonly<Record<string, ComponentType<ScreenProps>>> = {
  "/": CommandCenterScreen,
  "/map": NetworkMapScreen,
  "/sensors": SensorsScreen,
  "/scenarios": ScenarioLabScreen,
  "/forecast": ForecastScreen,
  "/decision": DecisionStudioScreen,
  "/runs": RunsScreen,
};
