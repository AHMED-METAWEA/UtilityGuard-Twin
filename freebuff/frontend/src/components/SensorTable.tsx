import type { EvidenceLabel, Frame, SensorMeta } from '../lib/types';
import { EvidenceBadge, Num } from './EvidenceBadge';

interface Props {
  sensors: SensorMeta[];
  frame: Frame | null;
  selectedSensor: string | null;
  onSelectSensor: (sensorId: string) => void;
}

const QUALITY_TEXT: Record<string, string> = {
  ok: 'ok',
  suspect: 'suspect',
  bad: 'bad',
};

export function SensorTable({ sensors, frame, selectedSensor, onSelectSensor }: Props) {
  const readings = new Map(frame?.readings.map((reading) => [reading.sensor_id, reading]) ?? []);
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Sensor</th>
            <th>Measures</th>
            <th>
              Value <EvidenceBadge label="SENSOR_SIM" />
            </th>
            <th>
              Data quality <EvidenceBadge label="MODEL" />
            </th>
            <th>
              Residual <EvidenceBadge label="MODEL" />
            </th>
            <th>Flags</th>
          </tr>
        </thead>
        <tbody>
          {sensors.map((sensor) => {
            const reading = readings.get(sensor.id);
            const residual = frame?.detector.residuals[sensor.id];
            return (
              <tr
                key={sensor.id}
                className={selectedSensor === sensor.id ? 'row-selected' : ''}
                onClick={() => onSelectSensor(sensor.id)}
              >
                <td>
                  <span className="mono strong">{sensor.id}</span>
                </td>
                <td className="muted">
                  {sensor.kind} · {sensor.target}
                </td>
                <td>
                  <Num value={reading?.value ?? null} unit={sensor.unit} label="SENSOR_SIM" digits={sensor.kind === 'level' ? 2 : 1} />
                </td>
                <td>
                  <span className={`pill pill-${reading?.quality.status === 'ok' ? 'good' : reading?.quality.status ?? 'muted'}`}>
                    {QUALITY_TEXT[reading?.quality.status ?? ''] ?? 'no reading'}
                  </span>
                  {reading ? (
                    <span className="muted small"> score {reading.quality.score.toFixed(2)}</span>
                  ) : null}
                </td>
                <td>
                  {residual === undefined ? (
                    <span className="muted">—</span>
                  ) : (
                    <span className={`mono ${Math.abs(residual) > 4 ? 'danger' : Math.abs(residual) > 2.5 ? 'warn' : ''}`}>
                      {residual > 0 ? '+' : ''}
                      {residual.toFixed(1)} σ <EvidenceBadge label={'MODEL' as EvidenceLabel} />
                    </span>
                  )}
                </td>
                <td className="muted small">
                  {reading?.quality.flags.length ? reading.quality.flags.join(', ') : '—'}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
