import type { EvidenceRecord, Input } from "../../generated/evidence-record";
import { decisionFixture } from "../../fixtures/decision";
import { Identifier } from "../../ui/Identifier";
import { Metric } from "../../ui/Metric";
import { Panel } from "../../ui/Panel";
import type { ScreenProps } from "../types";
import { DECISION_STRINGS as S } from "./strings";
import "./decision.css";

function Value({ record, range = false }: { record: EvidenceRecord; range?: boolean }) {
  return <Metric value={record.value} unit={record.unit} label={record.label} evidence={record} range={range ? record.uncertainty : undefined} />;
}
function sourceRecord(input: Input): EvidenceRecord {
  return decisionFixture.supportingEvidence.find(record => record.evidence_id === input.ref)!;
}
const data = decisionFixture.comparison;
function evidence(id: string): EvidenceRecord {
  const record = data.evidence.find(item => item.evidence_id === id);
  if (!record) throw new Error(`Missing fixture evidence: ${id}`);
  return record;
}
function delayRecord(option: typeof data.options[number]): EvidenceRecord {
  return { schema_version: "1", evidence_id: `${option.option_id}:delay`, value: option.delay_hours, unit: S.units.hours,
    label: "ASSUMPTION", formula: null, inputs: [], provenance: { assumption_set: data.assumption_set }, explanation_template: "fixture.delay.v1", reason: S.scope };
}
export function DecisionStudioScreen({ route }: ScreenProps) {
  return <div className="ug-decision">
    <h1>{S.title}</h1><p className="ug-decision-fixture">{S.fixture}</p>
    <p className="ug-decision-advisory">{S.advisory}</p><p>{S.scope}</p>
    <Panel title={S.waiting}><p>{S.waitingDetail}</p><Value record={decisionFixture.waitingCost} range /><p>{S.quantiles}{" "}<Identifier text="p10 / p50 / p90" /></p></Panel>
    <Panel title={S.options}><div className="ug-decision-scroll"><table>
      <thead><tr><th scope="col">{S.option}</th><th scope="col">{S.delay}</th><th scope="col">{S.expected}</th><th scope="col">{S.worst}{" "}<Identifier text="p90" /></th><th scope="col">{S.regret}</th></tr></thead>
      <tbody>{data.options.map(option => <tr key={option.option_id} data-lowest={option.option_id === data.preferred_by_expected_cost}>
        <th scope="row"><Identifier text={option.option_id} /><div>{S.actions[option.action]}</div>{option.option_id === data.preferred_by_expected_cost && <strong className="ug-decision-lowest">{S.lowest}</strong>}</th>
        <td><Value record={delayRecord(option)} /></td>
        <td><Value record={evidence(option.expected_cost)} /></td><td><Value record={evidence(option.worst_case)} /></td><td><Value record={evidence(option.expected_regret)} /></td>
      </tr>)}</tbody>
    </table></div><p>{S.aggregate}</p></Panel>
    <Panel title={S.lines}><div className="ug-decision-grid">{data.options.map(option => <section key={option.option_id}>
      <h3><Identifier text={option.option_id} /></h3><ul>{option.cost_lines.map(id => {
        const record = evidence(id), category = id.split(":")[1] as keyof typeof S.categories;
        return <li key={id}><span>{S.categories[category]}</span><div className="ug-decision-equation">
          <Value record={sourceRecord(record.inputs[0]!)} />{S.multiply}<Value record={sourceRecord(record.inputs[1]!)} />{S.equals}<Value record={record} />
        </div></li>;
      })}</ul>
    </section>)}</div></Panel>
    <Panel title={S.net}><ul>{decisionFixture.netBenefits.map(item => <li key={item.option_id}>
      {S.actions.fix_now}{" "}{S.versus}{" "}<Identifier text={item.option_id} />{": "}
      <span data-testid={`net-${item.option_id}`}>{Number(item.evidence.value) > 0 ? "+" : ""}<Value record={item.evidence} /></span>
    </li>)}</ul></Panel>
    <Panel title={S.breakEven}><p>{S.breakPrefix}{" "}<Value record={decisionFixture.breakEven} />{" "}{S.breakSuffix}</p></Panel>
    <details><summary>{S.integration}</summary><p>{S.runContext}</p><p>{route.empty}</p></details>
  </div>;
}
