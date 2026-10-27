import { linePath } from "./geometry";
import type { ChartPoint } from "./geometry";
import { CHART_STRINGS as S } from "./strings";
import "./charts.css";

export function Sparkline({ points, title = S.sparkline }: { points: readonly ChartPoint[]; title?: string }) {
  const values = points.flatMap((p) => p.value !== null && Number.isFinite(p.value) ? [p.value] : []);
  const min = values.length ? Math.min(...values) : 0, max = values.length ? Math.max(...values) : 1;
  const first = points[0]?.tick ?? 0, last = points.at(-1)?.tick ?? 1;
  return <svg className="ug-sparkline" viewBox="0 0 100 28" role="img" aria-label={title}>
    <path className="ug-chart-line" d={linePath(points, (tick) => 2 + (tick - first) / (last - first || 1) * 96, (value) => 25 - (value - min) / (max - min || 1) * 22)} />
  </svg>;
}
