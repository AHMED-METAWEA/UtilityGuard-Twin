import { useMemo } from "react";
import type { EvidenceRecord } from "../../generated/evidence-record";
import { replayTick, useReplay } from "../../app/api";
import type { Replay } from "../../app/api";
import { createCommandFixture, tickTime } from "../../fixtures/command";
import { Identifier } from "../../ui/Identifier";
import { Metric } from "../../ui/Metric";
import { Panel } from "../../ui/Panel";
import { NetworkMap } from "../map/NetworkMapScreen";
import type { ScreenProps } from "../types";
import { COMMAND_STRINGS as S } from "./strings";
import "./command.css";

function EvidenceMetric({ record }: { record: EvidenceRecord }) {
  return <Metric value={record.value} unit={record.unit} label={record.label} evidence={record} range={record.uncertainty} />;
}

function RecordedCommand({ title, replay }: { title: string; replay: Replay }) {
  return <div className="ug-command">
    <div className="ug-command-header">
      <div><p className="ug-command-eyebrow">{S.eyebrow}</p><h1>{title}</h1><p>{S.subtitle}</p></div>
    </div>
    <div className="ug-command-status"><span>{S.recorded} <Identifier text={replay.runId} /></span></div>
    <div className="ug-command-layout">
      <div className="ug-command-network"><Panel title={S.network}>
        <NetworkMap fixture={false} network={replay.network} state={replayTick(replay)} candidates={[]} />
        <a className="ug-command-link" href="#/map">{S.mapLink}</a>
      </Panel></div>
      <div className="ug-command-sidebar">
        <Panel title={S.alerts}><p>{S.replayAlerts}</p></Panel>
        <Panel title={S.latest}>
          <p>{S.caveat}</p>
          <section aria-label={S.readings}><dl>{replay.series.map((series) => {
            const last = series.values.at(-1);
            return <div key={series.series_id}><dt><Identifier text={series.series_id} /></dt>
              <dd data-evidence-label={series.label}>{last == null ? S.unavailable : `${last.toFixed(2)} ${series.unit}`}{S.separator}{series.label}</dd></div>;
          })}</dl></section>
        </Panel>
      </div>
    </div>
  </div>;
}

export function CommandCenterScreen({ route }: ScreenProps) {
  const { replay, reason } = useReplay();
  if (replay) return <RecordedCommand title={route.title} replay={replay} />;
  return <FixtureCommand route={route} reason={reason} />;
}

function FixtureCommand({ route, reason }: Pick<ScreenProps, "route"> & { reason: string }) {
  const fixture = useMemo(createCommandFixture, []);
  const incidents = fixture.incidents.filter((incident) => incident.status === "open");
  const top = incidents[0]!;
  const clock = tickTime(fixture.tick);
  return <div className="ug-command">
    <div className="ug-command-header">
      <div><p className="ug-command-eyebrow">{S.eyebrow}</p><h1>{route.title}</h1><p>{S.subtitle}</p></div>
      <div className="ug-command-clock" aria-label={S.clock}>
        <span>{S.clock}</span><time dateTime={clock.dateTime}>{clock.text}</time><small>{S.clockNote}</small>
      </div>
    </div>
    <div className="ug-command-status"><span className="ug-fixture-marker">{S.fixture}</span>{reason && <span role="status">{reason}</span>}
      <details><summary>{S.runConnection}</summary><p>{route.empty}</p><p>{S.fixtureExplanation}</p></details>
    </div>
    <section className="ug-command-kpis" aria-label={S.kpis}>
      {(["demand", "delivered", "pressure", "tanks", "flags"] as const).map((key) => <div key={key}>
        <h2>{S[key]}</h2><EvidenceMetric record={fixture.kpis[key]} />
      </div>)}
    </section>
    <div className="ug-command-layout">
      <div className="ug-command-network"><Panel title={S.network}>
        <NetworkMap network={fixture.network} state={fixture.state} candidates={top.location.candidates} />
        <a className="ug-command-link" href="#/map">{S.mapLink}</a>
      </Panel></div>
      <div className="ug-command-sidebar">
        <Panel title={S.alerts}>
          {incidents.map((incident) => {
            const detected = tickTime(incident.first_detected_tick);
            return <article className="ug-command-incident" data-severity={incident.severity} key={incident.incident_id}>
              <div className="ug-command-incident-heading"><h3>{S.hypotheses[incident.hypothesis]}</h3><Identifier text={incident.incident_id} /></div>
              <dl className="ug-command-incident-meta">
                <div><dt>{S.support}</dt><dd className="ug-command-support">{incident.support}</dd></div>
                <div><dt>{S.severity}</dt><dd>{incident.severity}</dd></div>
                <div><dt>{S.detected}</dt><dd><time dateTime={detected.dateTime}>{detected.text}</time></dd></div>
                <div><dt>{S.zone}</dt><dd>{incident.location.zone_id ? <Identifier text={incident.location.zone_id} /> : S.noZone}</dd></div>
              </dl>
              <h4>{S.candidates}</h4><p className="ug-command-score-note">{S.score}</p>
              <ul className="ug-command-candidates">{[...incident.location.candidates].sort((a, b) => b.score - a.score || a.asset_id.localeCompare(b.asset_id, "en")).slice(0, 3).map((candidate) => <li key={candidate.asset_id}>
                <Identifier text={candidate.asset_id} /><EvidenceMetric record={fixture.candidateEvidence[`${incident.incident_id}:${candidate.asset_id}`]!} />
              </li>)}</ul>
              {!incident.location.candidates.length && <p>{S.noCandidates}</p>}
            </article>;
          })}
        </Panel>
        <Panel title={S.cost}>
          <p className="ug-command-cost-context"><Identifier text={top.incident_id} />{S.hypotheses[top.hypothesis]}</p>
          <h3>{S.hourlyCost}</h3><EvidenceMetric record={fixture.cost} />
          <p className="ug-command-cost-basis">{S.costBasis}</p><p className="ug-command-advisory">{S.advisory}</p>
          <a className="ug-command-link" href="#/decision">{S.decision}</a>
        </Panel>
      </div>
    </div>
  </div>;
}
