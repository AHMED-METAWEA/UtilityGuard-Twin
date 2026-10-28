export const FORECAST_STRINGS = {
  integration: "Run integration", runContext: "The panels above use local fixture data. Run-backed data is not connected here yet.",
  title: "Forecast and Early Warning", fixture: "Fixture data, not a run",
  demand: "Zone demand and measured inlet flow", tanks: "Tank levels and thresholds",
  demandSeries: "Demand forecast", inletSeries: "Measured inlet flow",
  tankSeries: "Measured tank level", forecastSeries: "Tank-level forecast", threshold: "Threshold",
  band: "Forecast band", lower: "Lower quantile", upper: "Upper quantile",
  time: "Time to threshold", trends: "Trend anomalies", trend: "Standardized sensor slope",
  scope: "Synthetic telemetry and model fixtures. Forecasts use telemetry and assumptions only.",
  notApproaching: "not approaching", stableReason: "The forecast slope is non-negative; the tank is not approaching the lower threshold.",
  fallingReason: "Linear continuation of the forecast slope to the assumed lower threshold; conditional on unchanged pump state and demand.",
  times: "Forecast starts at", units: { flow: "m3/h", level: "m", hours: "h", slope: "sigma/h" },
} as const;
