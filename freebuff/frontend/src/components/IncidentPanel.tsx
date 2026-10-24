import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import type { EvidenceBundle, Incident } from '../lib/types';
import { EvidenceBadge } from './EvidenceBadge';

interface Props {
  incidents: Incident[];
  selected: Incident | null;
  onSelect: (incident: Incident | null) => void;
  onAnalyze: (incident: Incident) => void;
  analyzing: boolean;
  currentTick: number;
}

function tickToClock(tick: number, timestepMinutes = 5): string {
  const totalMinutes = tick * timestepMinutes;
  const day = Math.floor(totalMinutes / 1440) + 1;
  const hour = Math.floor((totalMinutes % 1440) / 60);
  const minute = totalMinutes % 60;
  return `day ${day} ${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`;
}

export function IncidentPanel({ incidents, selected, onSelect, onAnalyze, analyzing, currentTick }: Props) {
  const [evidence, setEvidence] = useState<EvidenceBundle | null>(null);
  const [evidenceError, setEvidenceError] = useState<string | null>(null);
  const [showAllNumbers, setShowAllNumbers] = useState(false);

  useEffect(() => {
    setEvidence(null);
    setEvidenceError(null);
    if (!selected) return;
    let cancelled = false;
    api
      .evidence(selected.id)
      .then((bundle) => {
        if (!cancelled) setEvidence(bundle);
      })
      .catch((error: Error) => {
        if (!cancelled) setEvidenceError(error.message);
      });
    return () => {
      cancelled = true;
    };
  }, [selected]);

  return (
    <div className="incident-layout">
      <div className="incident-list">
        {incidents.length === 0 ? (
          <div className="empty-state">
            <strong>No incidents opened.</strong>
            <p>
              The detector has not met its persistence rules. An empty list on a fault scenario is a missed detection, not a
              guarantee that nothing happened.
            </p>
          </div>
        ) : (
          incidents.map((incident) => (
            <button
              key={incident.id}
              className={`incident-card ${selected?.id === incident.id ? 'incident-card-selected' : ''} severity-${incident.severity}`}
              onClick={() => onSelect(incident)}
            >
              <div className="incident-card-head">
                <span className={`pill pill-${incident.severity}`}>{incident.severity}</span>
                <span className="mono small">{incident.diagnosis.replace(/_/g, ' ')}</span>
              </div>
              <div className="incident-card-location">
                {incident.suspected_location ?? 'location not localised'}
              </div>
              <div className="muted small">
                opened {tickToClock(incident.first_detected_tick)} · last {tickToClock(incident.last_tick)}
                {currentTick < incident.first_detected_tick ? ' · not yet detected at playhead' : ''}
              </div>
            </button>
          ))
        )}
      </div>

      <div className="incident-detail">
        {!selected ? (
          <div className="empty-state">
            <strong>Select an incident</strong>
            <p>Evidence, rule trace and the cost analysis for the selected incident appear here.</p>
          </div>
        ) : (
          <>
            <div className="detail-head">
              <div>
                <div className="eyebrow">Incident {selected.id}</div>
                <h3>
                  {selected.diagnosis.replace(/_/g, ' ')} <EvidenceBadge label="MODEL" />
                </h3>
              </div>
              <button className="btn" onClick={() => onAnalyze(selected)} disabled={analyzing}>
                {analyzing ? 'Simulating options…' : 'Compare response costs'}
              </button>
            </div>

            <div className="kv-grid">
              <div>
                <span className="kv-label">Severity</span>
                <span className={`pill pill-${selected.severity}`}>{selected.severity}</span>
              </div>
              <div>
                <span className="kv-label">Suspected location</span>
                <span className="mono">{selected.suspected_location ?? 'not localised'}</span>
              </div>
              <div>
                <span className="kv-label">Rule strength</span>
                <span className="mono">{selected.strength}</span>
              </div>
              <div>
                <span className="kv-label">First detected</span>
                <span className="mono">
                  tick {selected.first_detected_tick} · {tickToClock(selected.first_detected_tick)}
                </span>
              </div>
            </div>

            <h4>Rules fired</h4>
            <ul className="rule-list">
              {selected.rules_fired.map((rule) => (
                <li key={rule}>{rule}</li>
              ))}
            </ul>

            {selected.candidates.length > 0 ? (
              <>
                <h4>
                  Candidate pipes <EvidenceBadge label="MODEL" />
                </h4>
                <div className="candidate-row">
                  {selected.candidates.map((candidate) => (
                    <div key={candidate.pipe} className="candidate">
                      <span className="mono">{candidate.pipe}</span>
                      <span className="muted small">score {candidate.score.toFixed(2)}</span>
                    </div>
                  ))}
                </div>
                <p className="muted small">
                  The score is a transparent geometric weighting of nearby pressure residuals. It is a ranking, not a
                  probability. On this looped grid, pressure-only localisation is weak: a leak&apos;s head loss spreads
                  across the network and the tank&apos;s common-mode drawdown dominates. Treat candidates as hypotheses
                  for a crew, never as a confirmed location.
                </p>
              </>
            ) : null}

            <h4>
              Evidence trace <EvidenceBadge label="MODEL" />
            </h4>
            {evidenceError ? <div className="error-box">{evidenceError}</div> : null}
            {!evidence && !evidenceError ? <div className="muted small">Loading evidence…</div> : null}
            {evidence ? (
              <>
                <div className="evidence-list">
                  {evidence.numbers.slice(0, showAllNumbers ? evidence.numbers.length : 8).map((record, index) => (
                    <details key={`${record.name}-${index}`} className="evidence-item">
                      <summary>
                        <span className="evidence-name">{record.name}</span>
                        <span className="mono">
                          {typeof record.value === 'number' ? record.value.toFixed(2) : String(record.value)} {record.unit}
                        </span>
                        <EvidenceBadge label={record.label} />
                      </summary>
                      <div className="evidence-body">
                        <div>
                          <span className="kv-label">Formula</span>
                          <pre className="formula">{record.formula}</pre>
                        </div>
                        <div>
                          <span className="kv-label">Explanation</span>
                          <p className="small">{record.explanation}</p>
                        </div>
                        {record.inputs.length ? (
                          <div>
                            <span className="kv-label">Inputs</span>
                            <ul className="input-list">
                              {record.inputs.map((input, inputIndex) => (
                                <li key={`${input.name}-${inputIndex}`}>
                                  <span>{input.name}</span>
                                  <EvidenceBadge label={input.label} />
                                  {input.value !== undefined && input.value !== null ? (
                                    <span className="mono small">
                                      {String(input.value)} {input.unit ?? ''}
                                    </span>
                                  ) : null}
                                </li>
                              ))}
                            </ul>
                          </div>
                        ) : null}
                      </div>
                    </details>
                  ))}
                </div>
                {evidence.numbers.length > 8 ? (
                  <button className="btn btn-subtle" onClick={() => setShowAllNumbers((value) => !value)}>
                    {showAllNumbers ? 'Show fewer' : `Show all ${evidence.numbers.length} evidence records`}
                  </button>
                ) : null}
                <details className="repro">
                  <summary>Reproducibility record</summary>
                  <pre className="formula">{JSON.stringify(evidence.reproducibility, null, 2)}</pre>
                </details>
              </>
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}
