import { fixtureEvidence, runFixture } from "../../fixtures/runs/manifest";
import { Identifier } from "../../ui/Identifier";
import { Metric } from "../../ui/Metric";
import { Panel } from "../../ui/Panel";
import type { ScreenProps } from "../types";
import { RUNS_STRINGS as S } from "./strings";
function Field({ name, id, value, unit = null }: { name: string; id: string; value: string | number | null; unit?: string | null }) {
  const evidence = fixtureEvidence(id, value, unit);
  return <div><dt>{name}</dt><dd><Metric value={value} unit={unit} label={evidence.label} evidence={evidence} /></dd></div>;
}
function IdentifierField({ name, value }: { name: string; value: string | number | null }) {
  return <div><dt>{name}</dt><dd>{value === null ? S.notAvailable : <Identifier text={String(value)} />}</dd></div>;
}
export function RunsScreen({ route }: ScreenProps) {
  const { manifest, runId, manifestHash } = runFixture;
  const config = manifest.config;
  return <>
    <h1>{route.title}</h1><p>{route.empty}</p><p>{S.intro}</p><p className="ug-fixture-marker">{S.fixture}</p>
    <Panel title={S.identity}><dl>
      <IdentifierField name={S.runId} value={runId} />
      <IdentifierField name={S.hash} value={manifestHash} />
      <IdentifierField name={S.seed} value={manifest.seed} />
    </dl></Panel>
    <Panel title={S.configuration}><dl>
      <IdentifierField name={S.scenario} value={config.scenario_id} />
      <IdentifierField name={S.network} value={config.network_version} />
      <IdentifierField name={S.sensors} value={config.sensor_set} />
      <div><dt>{S.start}</dt><dd><time dateTime={config.start}>{config.start}</time></dd></div>
      <Field name={S.duration} id="duration" value={config.duration_hours} unit={S.hours} />
      <Field name={S.timestep} id="timestep" value={config.timestep_minutes} unit={S.minutes} />
      <IdentifierField name={S.assumptions} value={config.assumption_set} />
    </dl></Panel>
    <Panel title={S.versions}><dl>
      <IdentifierField name={S.contract} value={manifest.schema_version} />
      {Object.entries(manifest.versions).map(([name, value]) => <IdentifierField key={name} name={name} value={value} />)}
      <IdentifierField name={S.commit} value={manifest.git_commit} />
    </dl></Panel>
  </>;
}
