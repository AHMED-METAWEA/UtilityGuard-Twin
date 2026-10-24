import type { Frame, Incident, NetworkDescription, TruthBundle } from '../lib/types';

interface Props {
  network: NetworkDescription;
  frame: Frame | null;
  incidents: Incident[];
  selectedIncident: Incident | null;
  truth: TruthBundle | null;
  showTruth: boolean;
  selectedSensor: string | null;
  onSelectSensor: (sensorId: string) => void;
}

const ZONE_BANDS = [
  { zone: 'gov', label: 'Government district', row: 0, rows: 2 },
  { zone: 'com', label: 'Commercial', row: 2, rows: 2 },
  { zone: 'res', label: 'Residential', row: 4, rows: 2 },
];

function pressureColor(value: number | null | undefined): string {
  if (value === null || value === undefined) return '#3d4654';
  if (value < 10) return '#ef4444';
  if (value < 15) return '#f59e0b';
  if (value < 20) return '#eab308';
  if (value < 30) return '#22c55e';
  return '#38bdf8';
}

function qualityColor(status: string | undefined): string {
  if (status === 'bad') return '#ef4444';
  if (status === 'suspect') return '#f59e0b';
  return '#22c55e';
}

export function NetworkMap({
  network,
  frame,
  incidents,
  selectedIncident,
  truth,
  showTruth,
  selectedSensor,
  onSelectSensor,
}: Props) {
  const nodeById = new Map(network.nodes.map((node) => [node.id, node]));
  const readings = new Map(frame?.readings.map((reading) => [reading.sensor_id, reading]) ?? []);
  const tick = frame?.tick ?? 0;
  const truthPressure = showTruth ? truth?.truth.pressure : undefined;
  const alertSensors = new Set(
    incidents
      .filter((incident) => incident.status === 'open')
      .flatMap((incident) => incident.sensors),
  );
  const candidatePipes = new Set(
    selectedIncident?.diagnosis === 'leak'
      ? selectedIncident.candidates.map((candidate) => candidate.pipe)
      : [],
  );
  const leakPipe = showTruth ? truth?.truth.leak_pipe ?? null : null;

  const rowY = (row: number) => 100 + row * 95;
  const bandHeight = 2 * 95;

  return (
    <div className="map-wrap">
      <svg viewBox="0 0 1000 760" className="map" role="img" aria-label="Hypothetical network map">
        <defs>
          <pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="6" stroke="rgba(255,255,255,0.08)" strokeWidth="1" />
          </pattern>
        </defs>

        {ZONE_BANDS.map((band) => (
          <g key={band.zone}>
            <rect
              x={110}
              y={rowY(band.row) - 42}
              width={600}
              height={bandHeight}
              rx={10}
              fill={band.zone === 'gov' ? 'rgba(56,189,248,0.05)' : band.zone === 'com' ? 'rgba(168,85,247,0.05)' : 'rgba(34,197,94,0.05)'}
              stroke="rgba(255,255,255,0.06)"
            />
            <text x={120} y={rowY(band.row) - 24} className="map-zone-label">
              {band.label}
            </text>
          </g>
        ))}

        {network.links.map((link) => {
          const start = nodeById.get(link.start);
          const end = nodeById.get(link.end);
          if (!start || !end) return null;
          const isCandidate = candidatePipes.has(link.id);
          const isLeak = leakPipe === link.id;
          const color = isLeak ? '#ef4444' : isCandidate ? '#fb923c' : link.kind === 'pipe' ? '#2f3d4f' : '#64748b';
          return (
            <g key={link.id}>
              <line
                x1={start.x}
                y1={start.y}
                x2={end.x}
                y2={end.y}
                stroke={color}
                strokeWidth={isLeak ? 7 : isCandidate ? 6 : link.kind === 'pipe' ? 3 : 4}
                strokeDasharray={isCandidate && !isLeak ? '8 5' : undefined}
                strokeLinecap="round"
                opacity={isCandidate || isLeak ? 0.95 : 0.75}
              >
                <title>
                  {link.id} · {link.kind}
                  {link.diameter_mm ? ` · DN${link.diameter_mm}` : ''}
                  {isLeak ? ' · simulated leak location (ground truth)' : ''}
                  {isCandidate ? ' · model leak candidate' : ''}
                </title>
              </line>
              {link.kind === 'pump' ? (
                <g>
                  <rect
                    x={(start.x + end.x) / 2 - 12}
                    y={(start.y + end.y) / 2 - 9}
                    width={24}
                    height={18}
                    rx={4}
                    fill="#0f172a"
                    stroke="#94a3b8"
                  />
                  <text x={(start.x + end.x) / 2} y={(start.y + end.y) / 2 + 4} className="map-symbol-label">
                    P
                  </text>
                </g>
              ) : null}
              {link.kind === 'valve' ? (
                <g>
                  <polygon
                    points={`${(start.x + end.x) / 2 - 8},${(start.y + end.y) / 2 - 7} ${(start.x + end.x) / 2 + 8},${(start.y + end.y) / 2} ${(start.x + end.x) / 2 - 8},${(start.y + end.y) / 2 + 7}`}
                    fill="#0f172a"
                    stroke="#94a3b8"
                    strokeWidth={1.4}
                  />
                </g>
              ) : null}
            </g>
          );
        })}

        {network.nodes.map((node) => {
          const value = truthPressure?.[node.id]?.[tick];
          const isTank = node.kind === 'tank';
          const isReservoir = node.kind === 'reservoir';
          return (
            <g key={node.id}>
              {isTank ? (
                <rect
                  x={node.x - 18}
                  y={node.y - 22}
                  width={36}
                  height={44}
                  rx={4}
                  fill={frame?.tank.level_m ? '#0b2a3d' : '#0f172a'}
                  stroke="#38bdf8"
                  strokeWidth={2}
                >
                  <title>
                    TANK1 · simulated level{' '}
                    {frame?.tank.level_m !== null && frame?.tank.level_m !== undefined
                      ? `${frame.tank.level_m.toFixed(2)} m`
                      : 'no reading'}
                  </title>
                </rect>
              ) : isReservoir ? (
                <rect x={node.x - 26} y={node.y - 16} width={52} height={32} rx={3} fill="#0b2a3d" stroke="#38bdf8" strokeWidth={2}>
                  <title>R1 · hypothetical source reservoir</title>
                </rect>
              ) : (
                <circle
                  cx={node.x}
                  cy={node.y}
                  r={7}
                  fill={showTruth ? pressureColor(value) : '#25313f'}
                  stroke={showTruth ? '#e2e8f0' : '#41546b'}
                  strokeWidth={1.4}
                >
                  <title>
                    {node.id} · {showTruth ? `simulated pressure ${value?.toFixed(1) ?? '—'} m` : 'junction'}
                  </title>
                </circle>
              )}
            </g>
          );
        })}

        {network.sensors.map((sensor) => {
          const reading = readings.get(sensor.id);
          const status = reading?.quality.status;
          const selected = selectedSensor === sensor.id;
          const alerting = alertSensors.has(sensor.id);
          return (
            <g
              key={sensor.id}
              className={`sensor ${selected ? 'sensor-selected' : ''} ${alerting ? 'sensor-alert' : ''}`}
              onClick={() => onSelectSensor(sensor.id)}
              role="button"
              tabIndex={0}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') onSelectSensor(sensor.id);
              }}
            >
              {alerting ? <circle cx={sensor.x} cy={sensor.y} r={15} className="sensor-ping" /> : null}
              <circle cx={sensor.x} cy={sensor.y} r={7.5} fill="#0b1220" stroke={qualityColor(status)} strokeWidth={2.5} />
              <text x={sensor.x + 12} y={sensor.y - 4} className="map-sensor-id">
                {sensor.id}
              </text>
              <text x={sensor.x + 12} y={sensor.y + 10} className="map-sensor-value">
                {reading?.value !== null && reading?.value !== undefined
                  ? `${reading.value.toFixed(sensor.kind === 'level' ? 2 : 1)} ${sensor.unit}`
                  : 'no reading'}
              </text>
              <title>
                {sensor.id} · {sensor.kind} on {sensor.target} · simulated measurement · quality: {status ?? 'n/a'}
              </title>
            </g>
          );
        })}

        <g transform="translate(120, 700)">
          <text x={0} y={0} className="map-legend-title">
            Junction pressure (twin ground truth, SIMULATION)
          </text>
          {[
            { color: '#ef4444', text: '< 10 m' },
            { color: '#f59e0b', text: '10–15 m' },
            { color: '#eab308', text: '15–20 m' },
            { color: '#22c55e', text: '20–30 m' },
            { color: '#38bdf8', text: '> 30 m' },
          ].map((item, index) => (
            <g key={item.text} transform={`translate(${index * 110}, 18)`}>
              <circle cx={5} cy={-4} r={5} fill={item.color} />
              <text x={15} y={0} className="map-legend">
                {item.text}
              </text>
            </g>
          ))}
          <text x={0} y={40} className="map-legend">
            Toggle “Twin ground truth” to colour junctions; sensor values stay simulated measurements.
          </text>
        </g>
      </svg>
    </div>
  );
}
