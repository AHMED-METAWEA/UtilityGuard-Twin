import type { EvidenceLabel } from "../../generated/common";
import { bandPath, linePath } from "./geometry";
import type { ChartPoint } from "./geometry";
import { CHART_STRINGS as S } from "./strings";
import "./charts.css";

export interface ChartSeries {
  id: string;
  name: string;
  unit: string;
  label: EvidenceLabel;
  points: readonly ChartPoint[];
}
export interface TimeSeriesChartProps {
  series: readonly ChartSeries[];
  title: string;
  nowTick?: number;
  tickMinutes?: number;
}

function elapsed(tick: number, minutes: number): string {
  const total = Math.round(tick * minutes);
  return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
}

/** Series share a physical unit; use separate charts for unlike units. Input order is tick order. */
export function TimeSeriesChart({ series, title, nowTick, tickMinutes = 5 }: TimeSeriesChartProps) {
  const points = series.flatMap((item) => [...item.points]);
  const ticks = points.map((p) => p.tick).filter(Number.isFinite);
  if (!ticks.length) return <p>{S.empty}</p>;
  const first = Math.min(...ticks), last = Math.max(...ticks);
  const values = points.flatMap((p) => [p.value, p.lower, p.upper]).filter((v): v is number => v != null && Number.isFinite(v));
  const min = values.length ? Math.min(...values) : 0;
  const max = values.length ? Math.max(...values) : 1;
  const pad = (max - min || Math.abs(max) || 1) * 0.1;
  const low = min - pad, high = max + pad;
  const x = (tick: number) => 72 + (tick - first) / (last - first || 1) * 640;
  const y = (value: number) => 224 - (value - low) / (high - low) * 192;
  return <figure className="ug-timeseries">
    <figcaption>{title}</figcaption>
    <svg viewBox="0 0 760 278" role="img" aria-label={title}>
      {series.map((item, index) => <g key={item.id} className={`ug-chart-series ug-chart-tone-${index % 3}`} data-series={item.id} data-evidence-label={item.label}>
        {index === 0 && values.length > 0 && [0, 0.5, 1].map((fraction) => {
          const value = low + fraction * (high - low);
          return <g key={fraction}>
            <line className="ug-chart-grid" x1="72" x2="712" y1={y(value)} y2={y(value)} />
            <text x="64" y={y(value) + 4} textAnchor="end" data-evidence-label={item.label}>{value.toFixed(1)}</text>
          </g>;
        })}
        {item.points.some((p) => p.lower != null && p.upper != null) && <path className="ug-chart-band" data-testid="range-band" d={bandPath(item.points, x, y)}><title>{S.range}</title></path>}
        <path className="ug-chart-line" data-testid="series-line" d={linePath(item.points, x, y)} />
        {item.points.filter((p) => p.flags?.length).map((p) => <g key={p.tick} data-testid="quality-marker">
          <circle className="ug-chart-flag" cx={x(p.tick)} cy={p.value === null ? 224 : y(p.value)} r="3">
            <title>{[S.flag, ...p.flags!.map((flag) => flag === "Q01" && p.value === null ? S.missing : Object.hasOwn(S.flags, flag) ? S.flags[flag as keyof typeof S.flags] : S.other)].join(S.separator)}</title>
          </circle>
        </g>)}
        {index === 0 && [0, 0.25, 0.5, 0.75, 1].map((fraction) => {
          const tick = first + (last - first) * fraction;
          return <text key={fraction} x={x(tick)} y="248" textAnchor="middle" data-evidence-label={item.label}>{elapsed(tick, tickMinutes)}</text>;
        })}
      </g>)}
      {nowTick !== undefined && nowTick >= first && nowTick <= last && <g data-testid="now-marker">
        <line className="ug-chart-now" x1={x(nowTick)} x2={x(nowTick)} y1="24" y2="228" />
        <text x={x(nowTick)} y="18" textAnchor="middle">{S.now}</text>
      </g>}
      <text x="392" y="272" textAnchor="middle">{S.time}</text>
    </svg>
    <ul className="ug-chart-legend">
      {series.map((item) => {
        const latest = item.points.at(-1);
        return <li key={item.id}>
          <code data-identifier>{item.name}</code>{S.separator}<span>{S.latest}</span>{S.space}
          <strong data-evidence-label={item.label}>{latest?.value != null ? latest.value.toFixed(2) : S.unavailable}</strong>{S.space}{item.unit}{S.separator}{item.label}
        </li>;
      })}
    </ul>
  </figure>;
}
