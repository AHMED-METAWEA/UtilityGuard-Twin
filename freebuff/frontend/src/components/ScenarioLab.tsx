import { useState } from 'react';
import type { Preset, RunSummary, ScenarioConfig } from '../lib/types';

interface Props {
  presets: Preset[];
  runs: RunSummary[];
  selectedPreset: string;
  selectedRunId: string | null;
  busy: boolean;
  onSelectPreset: (scenarioId: string) => void;
  onStart: (config: ScenarioConfig) => void;
  onOpenRun: (runId: string) => void;
}

type FaultDraft = {
  leak: boolean;
  pipe: number;
  startHour: number;
  area: number;
  profile: 'gradual' | 'sudden';
  rampHours: number;
  drift: boolean;
  driftSensor: string;
  driftPerHour: number;
  pump: boolean;
  pumpStart: number;
  pumpDuration: number;
};

const initialDraft: FaultDraft = {
  leak: true,
  pipe: 17,
  startHour: 12,
  area: 6,
  profile: 'gradual',
  rampHours: 24,
  drift: false,
  driftSensor: 'P05',
  driftPerHour: 0.3,
  pump: false,
  pumpStart: 18,
  pumpDuration: 4,
};

function buildCustom(draft: FaultDraft, duration: number): ScenarioConfig {
  const faults: Record<string, unknown>[] = [];
  if (draft.leak) {
    faults.push({
      type: 'leak',
      location: `pipe:PIPE_${String(draft.pipe).padStart(2, '0')}`,
      start_hour: draft.startHour,
      profile: draft.profile,
      ramp_hours: draft.profile === 'gradual' ? draft.rampHours : 0,
      final_area_cm2: draft.area,
    });
  }
  if (draft.drift) {
    faults.push({ type: 'sensor_drift', sensor_id: draft.driftSensor, start_hour: draft.startHour, drift_per_hour: draft.driftPerHour });
  }
  if (draft.pump) {
    faults.push({ type: 'pump_outage', pump_id: 'PUMP_1', start_hour: draft.pumpStart, duration_hours: draft.pumpDuration });
  }
  return {
    scenario_id: 'custom',
    network_version: 'ugtwin-v1',
    seed: 4242,
    duration_hours: duration,
    timestep_minutes: 5,
    demand: { holiday: false, heatwave_multiplier: 1, zone_multipliers: { gov: 1, res: 1, com: 1 } },
    faults,
  } as ScenarioConfig;
}

export function ScenarioLab({
  presets,
  runs,
  selectedPreset,
  selectedRunId,
  busy,
  onSelectPreset,
  onStart,
  onOpenRun,
}: Props) {
  const [mode, setMode] = useState<'preset' | 'custom'>('preset');
  const [draft, setDraft] = useState<FaultDraft>(initialDraft);
  const [duration, setDuration] = useState(48);

  const update = <K extends keyof FaultDraft>(key: K, value: FaultDraft[K]) =>
    setDraft((current) => ({ ...current, [key]: value }));

  return (
    <aside className="scenario-lab">
      <div className="tabs tabs-small">
        <button className={mode === 'preset' ? 'tab tab-active' : 'tab'} onClick={() => setMode('preset')}>
          Presets
        </button>
        <button className={mode === 'custom' ? 'tab tab-active' : 'tab'} onClick={() => setMode('custom')}>
          Custom
        </button>
      </div>

      {mode === 'preset' ? (
        <div className="preset-list">
          {presets.map((preset) => (
            <button
              key={preset.scenario_id}
              className={`preset ${selectedPreset === preset.scenario_id ? 'preset-selected' : ''}`}
              onClick={() => onSelectPreset(preset.scenario_id)}
            >
              <span className="preset-name">{preset.scenario_id.replace(/_/g, ' ')}</span>
              <span className="preset-note">{preset.note}</span>
            </button>
          ))}
        </div>
      ) : (
        <div className="custom-form">
          <label className="field">
            <span>Duration (h)</span>
            <select className="select" value={duration} onChange={(event) => setDuration(Number(event.target.value))}>
              <option value={12}>12</option>
              <option value={24}>24</option>
              <option value={48}>48</option>
            </select>
          </label>
          <label className="check">
            <input type="checkbox" checked={draft.leak} onChange={(event) => update('leak', event.target.checked)} />
            Pipe leak
          </label>
          {draft.leak ? (
            <div className="sub-form">
              <label className="field">
                <span>Pipe number</span>
                <input
                  className="input"
                  type="number"
                  min={1}
                  max={60}
                  value={draft.pipe}
                  onChange={(event) => update('pipe', Math.min(60, Math.max(1, Number(event.target.value))))}
                />
              </label>
              <label className="field">
                <span>Start hour</span>
                <input
                  className="input"
                  type="number"
                  min={0}
                  max={duration - 1}
                  value={draft.startHour}
                  onChange={(event) => update('startHour', Number(event.target.value))}
                />
              </label>
              <label className="field">
                <span>Final area (cm²)</span>
                <input
                  className="input"
                  type="number"
                  min={0.2}
                  max={40}
                  step={0.2}
                  value={draft.area}
                  onChange={(event) => update('area', Number(event.target.value))}
                />
              </label>
              <label className="field">
                <span>Profile</span>
                <select
                  className="select"
                  value={draft.profile}
                  onChange={(event) => update('profile', event.target.value as 'gradual' | 'sudden')}
                >
                  <option value="gradual">gradual</option>
                  <option value="sudden">sudden</option>
                </select>
              </label>
              {draft.profile === 'gradual' ? (
                <label className="field">
                  <span>Ramp (h)</span>
                  <input
                    className="input"
                    type="number"
                    min={1}
                    max={duration}
                    value={draft.rampHours}
                    onChange={(event) => update('rampHours', Number(event.target.value))}
                  />
                </label>
              ) : null}
            </div>
          ) : null}

          <label className="check">
            <input type="checkbox" checked={draft.drift} onChange={(event) => update('drift', event.target.checked)} />
            Pressure sensor drift
          </label>
          {draft.drift ? (
            <div className="sub-form">
              <label className="field">
                <span>Sensor</span>
                <select className="select" value={draft.driftSensor} onChange={(event) => update('driftSensor', event.target.value)}>
                  {['P01', 'P02', 'P03', 'P04', 'P05', 'P06', 'P07', 'P08'].map((sensor) => (
                    <option key={sensor} value={sensor}>
                      {sensor}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Drift m/h</span>
                <input
                  className="input"
                  type="number"
                  step={0.1}
                  value={draft.driftPerHour}
                  onChange={(event) => update('driftPerHour', Number(event.target.value))}
                />
              </label>
            </div>
          ) : null}

          <label className="check">
            <input type="checkbox" checked={draft.pump} onChange={(event) => update('pump', event.target.checked)} />
            Duty pump outage
          </label>
          {draft.pump ? (
            <div className="sub-form">
              <label className="field">
                <span>Start hour</span>
                <input
                  className="input"
                  type="number"
                  min={0}
                  max={duration - 1}
                  value={draft.pumpStart}
                  onChange={(event) => update('pumpStart', Number(event.target.value))}
                />
              </label>
              <label className="field">
                <span>Duration (h)</span>
                <input
                  className="input"
                  type="number"
                  min={0.5}
                  step={0.5}
                  value={draft.pumpDuration}
                  onChange={(event) => update('pumpDuration', Number(event.target.value))}
                />
              </label>
            </div>
          ) : null}
        </div>
      )}

      <button
        className="btn btn-primary btn-wide"
        disabled={busy}
        onClick={() => onStart(mode === 'preset' ? presets.find((p) => p.scenario_id === selectedPreset)?.config ?? presets[0]?.config : buildCustom(draft, duration))}
      >
        {busy ? 'Simulating…' : 'Run scenario'}
      </button>

      <h4 className="history-title">Recent runs</h4>
      <div className="run-list">
        {runs.length === 0 ? <div className="muted small">No runs yet.</div> : null}
        {runs.map((run) => (
          <button
            key={run.run_id}
            className={`run-item ${selectedRunId === run.run_id ? 'run-item-selected' : ''}`}
            onClick={() => onOpenRun(run.run_id)}
          >
            <div className="run-item-head">
              <span>{run.scenario_id.replace(/_/g, ' ')}</span>
              <span className={`pill pill-${run.status === 'ready' ? 'good' : run.status === 'error' ? 'bad' : 'suspect'}`}>
                {run.status}
              </span>
            </div>
            <div className="muted small mono">{run.run_id.slice(0, 8)}</div>
          </button>
        ))}
      </div>
    </aside>
  );
}
