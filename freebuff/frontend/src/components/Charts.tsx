import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

export interface SeriesPoint {
  tick: number;
  time: string;
  tank: number | null;
  residual: number | null;
  value: number | null;
  flowOut: number | null;
  flowPump: number | null;
}

interface Props {
  series: SeriesPoint[];
  sensorLabel: string;
  sensorUnit: string;
}

const tooltipStyle = {
  background: '#0b1220',
  border: '1px solid #24344a',
  borderRadius: 8,
  fontSize: 12,
  color: '#e2e8f0',
};

export function Charts({ series, sensorLabel, sensorUnit }: Props) {
  const residuals = series
    .map((point) => point.residual)
    .filter((value): value is number => value !== null && Number.isFinite(value));
  const residualLow = Math.floor(Math.min(-5, ...residuals) - 1);
  const residualHigh = Math.ceil(Math.max(5, ...residuals) + 1);
  return (
    <div className="charts">
      <div className="chart-card">
        <div className="chart-title">
          Tank level <span className="ev ev-sensor-sim">sensor</span>
        </div>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={series} margin={{ top: 8, right: 12, bottom: 0, left: -18 }}>
            <CartesianGrid stroke="#1c2a3a" strokeDasharray="3 3" />
            <XAxis dataKey="time" tick={{ fill: '#7d8ea3', fontSize: 10 }} minTickGap={40} />
            <YAxis tick={{ fill: '#7d8ea3', fontSize: 10 }} domain={[0, 8]} />
            <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: '#9fb2c8' }} />
            <Line type="monotone" dataKey="tank" stroke="#38bdf8" dot={false} strokeWidth={2} name="T01 level (m)" />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="chart-card">
        <div className="chart-title">
          {sensorLabel} <span className="ev ev-sensor-sim">sensor</span>
        </div>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={series} margin={{ top: 8, right: 12, bottom: 0, left: -18 }}>
            <CartesianGrid stroke="#1c2a3a" strokeDasharray="3 3" />
            <XAxis dataKey="time" tick={{ fill: '#7d8ea3', fontSize: 10 }} minTickGap={40} />
            <YAxis tick={{ fill: '#7d8ea3', fontSize: 10 }} unit={sensorUnit} />
            <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: '#9fb2c8' }} />
            <Line type="monotone" dataKey="value" stroke="#22c55e" dot={false} strokeWidth={2} name={`reading (${sensorUnit})`} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="chart-card">
        <div className="chart-title">
          Residual vs fault-free twin <span className="ev ev-model">model</span>
        </div>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={series} margin={{ top: 8, right: 12, bottom: 0, left: -18 }}>
            <CartesianGrid stroke="#1c2a3a" strokeDasharray="3 3" />
            <XAxis dataKey="time" tick={{ fill: '#7d8ea3', fontSize: 10 }} minTickGap={40} />
            <YAxis tick={{ fill: '#7d8ea3', fontSize: 10 }} unit="σ" domain={[residualLow, residualHigh]} />
            <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: '#9fb2c8' }} />
            <ReferenceLine y={4} stroke="#ef4444" strokeDasharray="4 4" />
            <ReferenceLine y={-4} stroke="#ef4444" strokeDasharray="4 4" />
            <ReferenceLine y={2.5} stroke="#f59e0b" strokeDasharray="2 4" />
            <ReferenceLine y={-2.5} stroke="#f59e0b" strokeDasharray="2 4" />
            <Line type="monotone" dataKey="residual" stroke="#a855f7" dot={false} strokeWidth={2} name="residual (σ)" />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="chart-card">
        <div className="chart-title">
          Flow sensors <span className="ev ev-sensor-sim">sensor</span>
        </div>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={series} margin={{ top: 8, right: 12, bottom: 0, left: -18 }}>
            <CartesianGrid stroke="#1c2a3a" strokeDasharray="3 3" />
            <XAxis dataKey="time" tick={{ fill: '#7d8ea3', fontSize: 10 }} minTickGap={40} />
            <YAxis tick={{ fill: '#7d8ea3', fontSize: 10 }} unit=" L/s" />
            <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: '#9fb2c8' }} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Line type="monotone" dataKey="flowOut" stroke="#f59e0b" dot={false} strokeWidth={2} name="F02 tank outflow" />
            <Line type="monotone" dataKey="flowPump" stroke="#38bdf8" dot={false} strokeWidth={2} name="F01 pump discharge" />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
