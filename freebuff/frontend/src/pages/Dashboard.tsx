import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AssumptionsPanel } from '../components/AssumptionsPanel';
import { Charts, type SeriesPoint } from '../components/Charts';
import { DecisionPanel } from '../components/DecisionPanel';
import { EvidenceBadge, Num } from '../components/EvidenceBadge';
import { IncidentPanel } from '../components/IncidentPanel';
import { NetworkMap } from '../components/NetworkMap';
import { Playback } from '../components/Playback';
import { ScenarioLab } from '../components/ScenarioLab';
import { SensorTable } from '../components/SensorTable';
import { api, openStream, type StreamControl } from '../lib/api';
import type {
  AssumptionsPayload,
  Decision,
  Frame,
  Incident,
  NetworkDescription,
  Preset,
  RunSummary,
  ScenarioConfig,
  TruthBundle,
} from '../lib/types';

type Tab = 'map-stream' | 'incidents' | 'decision' | 'assumptions' | 'method';

const TABS: { id: Tab; label: string }[] = [
  { id: 'map-stream', label: 'Stream & sensors' },
  { id: 'incidents', label: 'Incidents & evidence' },
  { id: 'decision', label: 'Costs & decision' },
  { id: 'assumptions', label: 'Assumptions' },
  { id: 'method', label: 'Method & limits' },
];

function formatTime(iso: string | null | undefined): string {
  return iso ? iso.replace('T', ' ').slice(0, 16) : '—';
}

export function Dashboard() {
  const [network, setNetwork] = useState<NetworkDescription | null>(null);
  const [presets, setPresets] = useState<Preset[]>([]);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [assumptions, setAssumptions] = useState<AssumptionsPayload | null>(null);
  const [selectedPreset, setSelectedPreset] = useState('normal');

  const [run, setRun] = useState<RunSummary | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  const [frames, setFrames] = useState<(Frame | null)[]>([]);
  const [tick, setTick] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(3600);
  const [streamState, setStreamState] = useState<'idle' | 'connecting' | 'live' | 'closed' | 'error'>('idle');

  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null);
  const [selectedSensor, setSelectedSensor] = useState<string>('P05');
  const [tab, setTab] = useState<Tab>('map-stream');

  const [decision, setDecision] = useState<Decision | null>(null);
  const [decisionLoading, setDecisionLoading] = useState(false);
  const [decisionError, setDecisionError] = useState<string | null>(null);

  const [truth, setTruth] = useState<TruthBundle | null>(null);
  const [showTruth, setShowTruth] = useState(false);

  const socketRef = useRef<WebSocket | null>(null);
  const selectedRunRef = useRef<string | null>(null);

  const send = useCallback((control: StreamControl) => {
    const socket = socketRef.current;
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify(control));
    }
  }, []);

  const loadIncidents = useCallback(async (runId: string) => {
    try {
      const payload = await api.incidents(runId);
      setIncidents(payload.incidents);
    } catch {
      setIncidents([]);
    }
  }, []);

  const openRun = useCallback(
    async (runId: string) => {
      if (selectedRunRef.current === runId && run?.status === 'ready') return;
      selectedRunRef.current = runId;
      socketRef.current?.close();
      socketRef.current = null;
      setStreamState('idle');
      setFrames([]);
      setTick(0);
      setPlaying(false);
      setIncidents([]);
      setSelectedIncident(null);
      setDecision(null);
      setDecisionError(null);
      setTruth(null);
      setShowTruth(false);
      setRunError(null);
      setRun((current) => (current && current.run_id === runId ? current : null));

      try {
        let detail = await api.run(runId);
        setRun(detail);
        let attempts = 0;
        while ((detail.status === 'queued' || detail.status === 'simulating') && attempts < 240) {
          await new Promise((resolve) => setTimeout(resolve, 500));
          detail = await api.run(runId);
          setRun(detail);
          attempts += 1;
        }
        if (detail.status !== 'ready') {
          setRunError(detail.error ?? `run is ${detail.status}`);
          return;
        }
        const framesArray: (Frame | null)[] = new Array(detail.ticks + 1).fill(null);
        setFrames(framesArray);
        await loadIncidents(runId);

        setStreamState('connecting');
        const socket = openStream(runId, speed);
        socketRef.current = socket;
        socket.onopen = () => {
          if (socketRef.current === socket) setStreamState('live');
        };
        socket.onmessage = (event) => {
          const frame = JSON.parse(event.data) as Frame & { type?: string; message?: string };
          if (frame.type === 'error') {
            setStreamState('error');
            setRunError(frame.message ?? 'stream error');
            return;
          }
          setFrames((current) => {
            if (!current.length) {
              const next: (Frame | null)[] = new Array(detail.ticks + 1).fill(null);
              next[frame.tick] = frame;
              return next;
            }
            if (next_exists(current, frame.tick)) {
              const next = current.slice();
              next[frame.tick] = frame;
              return next;
            }
            return current;
          });
          setTick(frame.tick);
          if (frame.tick >= detail.ticks) setPlaying(false);
          if (frame.alerts_changed && frame.alerts_changed.length > 0) {
            void loadIncidents(runId);
          }
        };
        socket.onclose = () => {
          if (socketRef.current === socket) {
            setStreamState((state) => (state === 'error' ? state : 'closed'));
            setPlaying(false);
          }
        };
        socket.onerror = () => {
          if (socketRef.current === socket) setStreamState('error');
        };
      } catch (error) {
        setRunError((error as Error).message);
      }
    },
    [loadIncidents, run?.status, speed],
  );

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.network(), api.scenarios(), api.runs(), api.assumptions()])
      .then(([networkData, scenarioData, runData, assumptionData]) => {
        if (cancelled) return;
        setNetwork(networkData);
        setPresets(scenarioData.presets);
        setRuns(runData.runs);
        setAssumptions(assumptionData);
        const ready = runData.runs.find((item) => item.status === 'ready');
        if (ready) {
          void openRun(ready.run_id);
        } else if (scenarioData.presets.length) {
          void startScenario(scenarioData.presets[0].config);
        }
      })
      .catch((error: Error) => setRunError(error.message));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => () => socketRef.current?.close(), []);

  const refreshRuns = useCallback(async () => {
    try {
      const payload = await api.runs();
      setRuns(payload.runs);
    } catch {
      // history is non-critical
    }
  }, []);

  const startScenario = useCallback(
    async (config: ScenarioConfig) => {
      setStarting(true);
      setRunError(null);
      setDecision(null);
      try {
        const created = await api.startRun({ config });
        await refreshRuns();
        selectedRunRef.current = null;
        await openRun(created.run_id);
        await refreshRuns();
      } catch (error) {
        setRunError((error as Error).message);
      } finally {
        setStarting(false);
      }
    },
    [openRun, refreshRuns],
  );

  const currentFrame = frames[tick] ?? null;
  const ticks = run?.ticks ?? 0;

  const series = useMemo<SeriesPoint[]>(() => {
    const points: SeriesPoint[] = [];
    frames.forEach((frame) => {
      if (!frame) return;
      const reading = frame.readings.find((item) => item.sensor_id === selectedSensor);
      const f01 = frame.readings.find((item) => item.sensor_id === 'F01');
      const f02 = frame.readings.find((item) => item.sensor_id === 'F02');
      points.push({
        tick: frame.tick,
        time: formatTime(frame.sim_time).slice(5),
        tank: frame.tank.level_m,
        residual: frame.detector.residuals[selectedSensor] ?? null,
        value: reading?.value ?? null,
        flowOut: f02?.value ?? null,
        flowPump: f01?.value ?? null,
      });
    });
    return points;
  }, [frames, selectedSensor]);

  const sensorMeta = network?.sensors.find((sensor) => sensor.id === selectedSensor) ?? null;

  const playheadIncidents = useMemo(
    () => incidents.filter((incident) => incident.first_detected_tick <= tick || tick >= ticks),
    [incidents, tick, ticks],
  );

  const qualityCounts = useMemo(() => {
    const counts = { ok: 0, suspect: 0, bad: 0 };
    currentFrame?.readings.forEach((reading) => {
      counts[reading.quality.status] += 1;
    });
    return counts;
  }, [currentFrame]);

  const pressureReadings = currentFrame?.readings.filter((reading) => reading.sensor_id.startsWith('P')) ?? [];
  const lowestPressure = pressureReadings.length
    ? pressureReadings.reduce((min, reading) =>
        (reading.value ?? Infinity) < (min.value ?? Infinity) ? reading : min,
      )
    : null;

  const togglePlay = () => {
    if (playing) {
      send({ action: 'pause' });
      setPlaying(false);
      return;
    }
    if (tick >= ticks) {
      send({ action: 'jump', value: 0 });
      send({ action: 'resume' });
    } else {
      send({ action: 'resume' });
    }
    setPlaying(true);
  };

  const changeSpeed = (value: number) => {
    setSpeed(value);
    send({ action: 'speed', value });
  };

  const seek = (value: number) => {
    setTick(value);
    send({ action: 'jump', value });
  };

  const analyzeIncident = async (incident: Incident) => {
    setTab('decision');
    setDecisionLoading(true);
    setDecisionError(null);
    setDecision(null);
    try {
      const result = await api.analyze(incident.id, {});
      setDecision(result);
    } catch (error) {
      setDecisionError((error as Error).message);
    } finally {
      setDecisionLoading(false);
    }
  };

  const toggleTruth = async () => {
    if (showTruth) {
      setShowTruth(false);
      return;
    }
    if (!run) return;
    try {
      if (!truth) {
        const data = await api.truth(run.run_id);
        setTruth(data);
      }
      setShowTruth(true);
    } catch (error) {
      setRunError((error as Error).message);
    }
  };

  if (!network) {
    return (
      <div className="boot">
        <div className="spinner" />
        <p>Loading the virtual network…</p>
        {runError ? <div className="error-box">{runError}</div> : null}
      </div>
    );
  }

  return (
    <div className="app">
      <header className="header">
        <div className="header-titles">
          <div>
            <div className="eyebrow">UtilityGuard Twin · prototype</div>
            <h1>Virtual water-network twin</h1>
          </div>
          <div className="header-meta">
            <span className="mono small">{network.network_version}</span>
            <span className="muted small">detector rules-v1</span>
          </div>
        </div>
        <div className="banner" role="note">
          <strong>Virtual utility twin. Hypothetical network, simulated data.</strong>
          <span>
            “Real-time” here is a replayed WNTR simulation. No real operator, customer or field data is used.
          </span>
        </div>
      </header>

      <div className="layout">
        <ScenarioLab
          presets={presets}
          runs={runs}
          selectedPreset={selectedPreset}
          selectedRunId={run?.run_id ?? null}
          busy={starting}
          onSelectPreset={setSelectedPreset}
          onStart={startScenario}
          onOpenRun={(runId) => {
            void openRun(runId);
          }}
        />

        <main className="main">
          <div className="run-bar">
            <div>
              <div className="eyebrow">Scenario {run?.scenario_id?.replace(/_/g, ' ') ?? '—'}</div>
              <div className="run-title">
                {run ? (
                  <>
                    {run.simulated_hours} simulated hours · {run.ticks} ticks <EvidenceBadge label="ASSUMPTION" />
                  </>
                ) : (
                  'No run loaded'
                )}
              </div>
            </div>
            <div className="run-meta">
              {run ? (
                <>
                  <span className={`pill pill-${run.status === 'ready' ? 'good' : run.status === 'error' ? 'bad' : 'suspect'}`}>
                    {run.status}
                  </span>
                  <span className="muted small mono">seed {run.seed}</span>
                  <span className="muted small mono">hash {(run.output_hash ?? '—').slice(0, 10)}</span>
                  <span className="muted small">runtime {run.runtime_seconds?.toFixed(1) ?? '—'} s</span>
                </>
              ) : (
                <span className="muted small">Choose a scenario and press Run.</span>
              )}
            </div>
          </div>

          {runError ? <div className="error-box">{runError}</div> : null}

          <div className="kpi-row">
            <div className="kpi">
              <span className="kpi-label">
                Detector <EvidenceBadge label="MODEL" />
              </span>
              <span className={`kpi-value state-${currentFrame?.detector.state ?? 'normal'}`}>
                {currentFrame?.detector.state ?? '—'}
              </span>
              <span className="muted small">{streamState === 'live' ? 'stream connected' : `stream ${streamState}`}</span>
            </div>
            <div className="kpi">
              <span className="kpi-label">
                Tank level <EvidenceBadge label="SENSOR_SIM" />
              </span>
              <Num value={currentFrame?.tank.level_m ?? null} label="SENSOR_SIM" unit="m" digits={2} className="kpi-value" />
              <span className="muted small">T01 simulated measurement</span>
            </div>
            <div className="kpi">
              <span className="kpi-label">
                Lowest pressure <EvidenceBadge label="SENSOR_SIM" />
              </span>
              <span className="kpi-value">
                {lowestPressure?.value !== null && lowestPressure?.value !== undefined
                  ? `${lowestPressure.value.toFixed(1)} m`
                  : '—'}
              </span>
              <span className="muted small">{lowestPressure?.sensor_id ?? '—'} · from 8 pressure sensors</span>
            </div>
            <div className="kpi">
              <span className="kpi-label">
                Data quality <EvidenceBadge label="MODEL" />
              </span>
              <span className="kpi-value">
                {qualityCounts.ok}/{currentFrame?.readings.length ?? 0} ok
              </span>
              <span className="muted small">
                {qualityCounts.suspect} suspect · {qualityCounts.bad} bad
              </span>
            </div>
            <div className="kpi">
              <span className="kpi-label">
                Incidents so far <EvidenceBadge label="MODEL" />
              </span>
              <span className="kpi-value">{playheadIncidents.length}</span>
              <span className="muted small">{incidents.length} in full offline analysis</span>
            </div>
          </div>

          <div className="map-card">
            <div className="map-toolbar">
              <span className="muted small">
                {currentFrame ? formatTime(currentFrame.sim_time) : '—'} · tick {tick}
              </span>
              <button className={`btn btn-subtle ${showTruth ? 'btn-active' : ''}`} onClick={() => void toggleTruth()}>
                {showTruth ? 'Twin ground truth: on' : 'Show twin ground truth'}
              </button>
            </div>
            <NetworkMap
              network={network}
              frame={currentFrame}
              incidents={playheadIncidents}
              selectedIncident={selectedIncident}
              truth={truth}
              showTruth={showTruth}
              selectedSensor={selectedSensor}
              onSelectSensor={(sensorId) => {
                setSelectedSensor(sensorId);
                setTab('map-stream');
              }}
            />
            <Playback
              tick={tick}
              ticks={ticks}
              playing={playing}
              speed={speed}
              simTime={currentFrame?.sim_time ?? null}
              status={run?.status ?? 'idle'}
              onToggle={togglePlay}
              onSpeed={changeSpeed}
              onSeek={seek}
            />
          </div>

          <div className="tabs">
            {TABS.map((item) => (
              <button
                key={item.id}
                className={tab === item.id ? 'tab tab-active' : 'tab'}
                onClick={() => setTab(item.id)}
              >
                {item.label}
              </button>
            ))}
          </div>

          <div className="tab-panel">
            {tab === 'map-stream' ? (
              <div className="stream-tab">
                <div className="quality-strip">
                  <div className="quality-card">
                    <div className="quality-title">
                      Readings flagged suspect or bad <EvidenceBadge label="MODEL" />
                    </div>
                    {currentFrame?.readings.some((reading) => reading.quality.status !== 'ok') ? (
                      <ul className="flag-list">
                        {currentFrame.readings
                          .filter((reading) => reading.quality.status !== 'ok')
                          .map((reading) => (
                            <li key={reading.sensor_id}>
                              <span className="mono">{reading.sensor_id}</span>
                              <span className={`pill pill-${reading.quality.status === 'suspect' ? 'suspect' : 'bad'}`}>
                                {reading.quality.status}
                              </span>
                              <span className="muted small">{reading.quality.flags.join(', ')}</span>
                            </li>
                          ))}
                      </ul>
                    ) : (
                      <p className="muted small">
                        No reading is flagged suspect or bad at this tick. Minor baseline deviations remain visible in the
                        table below.
                      </p>
                    )}
                  </div>
                  <div className="quality-card">
                    <div className="quality-title">Scenario faults (declared ASSUMPTIONs)</div>
                    <p className="muted small">
                      Scenario faults are declared in the run config as ASSUMPTIONs. Detector sees only simulated readings;
                      twin ground truth is never an input to detection.
                    </p>
                    <ul className="fault-list">
                      {(run?.config.faults ?? []).length === 0 ? <li className="muted small">No faults in this scenario.</li> : null}
                      {(run?.config.faults ?? []).map((fault, index) => (
                        <li key={index} className="mono small">
                          {String(fault.type).replace(/_/g, ' ')} · {String(fault.location ?? fault.sensor_id ?? fault.pump_id)} ·{' '}
                          start h{String(fault.start_hour)}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
                <SensorTable
                  sensors={network.sensors}
                  frame={currentFrame}
                  selectedSensor={selectedSensor}
                  onSelectSensor={setSelectedSensor}
                />
                <Charts
                  series={series}
                  sensorLabel={`${selectedSensor} · ${sensorMeta?.kind ?? ''} ${sensorMeta?.target ?? ''}`}
                  sensorUnit={sensorMeta?.unit ?? ''}
                />
              </div>
            ) : null}

            {tab === 'incidents' ? (
              <IncidentPanel
                incidents={playheadIncidents}
                selected={selectedIncident}
                onSelect={setSelectedIncident}
                onAnalyze={(incident) => {
                  setSelectedIncident(incident);
                  void analyzeIncident(incident);
                }}
                analyzing={decisionLoading}
                currentTick={tick}
              />
            ) : null}

            {tab === 'decision' ? (
              <DecisionPanel
                decision={decision}
                loading={decisionLoading}
                error={decisionError}
                hasIncident={Boolean(selectedIncident)}
                onAnalyze={() => {
                  if (selectedIncident) void analyzeIncident(selectedIncident);
                  else setTab('incidents');
                }}
              />
            ) : null}

            {tab === 'assumptions' ? <AssumptionsPanel data={assumptions} onSaved={setAssumptions} /> : null}

            {tab === 'method' ? <MethodPanel network={network} /> : null}
          </div>
        </main>
      </div>
    </div>
  );
}

function next_exists(frames: (Frame | null)[], tick: number): boolean {
  return tick >= 0 && tick < frames.length;
}

function MethodPanel({ network }: { network: NetworkDescription }) {
  return (
    <div className="method">
      <h3>What this prototype is</h3>
      <p>
        A hypothetical 36-junction, three-zone distribution grid with a reservoir, duty/standby pumps, an elevated tank, a
        pressure-reducing valve and three isolation valves. WNTR solves the hydraulics with pressure-dependent demand. A
        separate sensor layer adds Gaussian noise and optional drift, stuck or dropout faults.
      </p>
      <h3>How the stream works</h3>
      <p>
        A whole scenario is simulated offline and stored. The WebSocket replays the stored frames at a selectable speed. No
        physics runs inside the stream, so replay is deterministic and cheap.
      </p>
      <h3>Evidence labels</h3>
      <ul className="label-legend">
        <li>
          <span className="ev ev-simulation">sim</span> WNTR output (ground truth of the twin)
        </li>
        <li>
          <span className="ev ev-sensor-sim">sensor</span> simulated measurement incl. noise and injected faults
        </li>
        <li>
          <span className="ev ev-model">model</span> quality layer, detector, diagnosis, ranking
        </li>
        <li>
          <span className="ev ev-assumption">assume</span> editable placeholder input (prices, demand curves, thresholds)
        </li>
        <li>
          <span className="ev ev-calculated">calc</span> arithmetic over other labelled values
        </li>
        <li>
          <span className="ev ev-insufficient-evidence">no evidence</span> not enough information; nothing is guessed
        </li>
      </ul>
      <h3>Network notes</h3>
      <ul>
        {network.notes.map((note) => (
          <li key={note}>{note}</li>
        ))}
      </ul>
      <h3>Limits</h3>
      <ul>
        <li>Leaks use a constant area per simulation chunk; gradual leaks are approximated by hourly chunks with tank carry-over.</li>
        <li>Isolation and repair are represented by a reduced leak area, not by valve operations on the graph.</li>
        <li>Costs use placeholder currency units and editable triangular ranges; they are not market figures.</li>
        <li>Detection rules were tuned on this synthetic network; no field validation exists.</li>
        <li>
          Pressure-only leak localisation is weak on this looped grid: measured top-3 accuracy is reported in
          docs/eval_report.md and is not good enough to dispatch a crew without further evidence.
        </li>
        <li>No failure probabilities are produced. The decision engine reports break-even thresholds instead.</li>
        <li>Sensor placement is a fixed synthetic design, not an optimisation result.</li>
      </ul>
    </div>
  );
}
